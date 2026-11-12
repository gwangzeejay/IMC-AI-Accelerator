"""INT8 DW/PW reference, TFLite two-rounding (gemmlowp) arithmetic.

Scope: NHWC batch=1, symmetric INT8 weights, depth multiplier=1,
dilation=1. Unsupported semantics are rejected rather than approximated.
"""
import math
import numpy as np

I32_MIN, I32_MAX = -(1 << 31), (1 << 31) - 1


def quantize_multiplier(scale):
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("positive finite multiplier required")
    fraction, shift = math.frexp(float(scale))
    q = int(math.floor(fraction * (1 << 31) + 0.5))
    if q == 1 << 31:
        q //= 2
        shift += 1
    if shift < -31:
        return 0, 0
    if shift > 30:
        raise ValueError("unsupported multiplier shift")
    return q, shift


def trunc_div(a, b):
    return (1 if a >= 0 else -1) * (abs(a) // b)


def high_mul(a, b):
    if a == b == I32_MIN:
        return I32_MAX
    product = int(a) * int(b)
    nudge = (1 << 30) if product >= 0 else 1 - (1 << 30)
    return trunc_div(product + nudge, 1 << 31)


def rounding_divide_pot(x, exponent):
    if exponent < 0 or exponent > 31:
        raise ValueError("invalid exponent")
    mask = (1 << exponent) - 1
    remainder = x & mask
    threshold = (mask >> 1) + int(x < 0)
    return (x >> exponent) + int(remainder > threshold)


def multiply_quantized(x, multiplier, shift):
    left = int(x) * (1 << max(shift, 0))
    if not I32_MIN <= left <= I32_MAX:
        raise OverflowError("INT32 left shift would overflow")
    return rounding_divide_pot(high_mul(left, multiplier), max(-shift, 0))


def requantize(acc, spec):
    acc = np.asarray(acc, dtype=np.int64)
    if np.any(acc < I32_MIN) or np.any(acc > I32_MAX):
        raise OverflowError("INT32 accumulator overflow")
    multipliers = spec['multipliers']
    shifts = spec['shifts']
    if len(multipliers) != acc.shape[-1] or len(shifts) != acc.shape[-1]:
        raise ValueError("per-channel quantization length mismatch")
    out = np.empty(acc.shape, dtype=np.int8)
    for index in np.ndindex(acc.shape):
        c = index[-1]
        value = multiply_quantized(int(acc[index]), multipliers[c], shifts[c])
        value += spec['output_zero_point']
        out[index] = max(spec['activation_min'], min(spec['activation_max'], value))
    return out


def validate_int8(x):
    if np.asarray(x).dtype != np.int8:
        raise TypeError("signed INT8 tensor required")


def accumulator_bound(weights, bias, input_zero_point):
    """Conservative all-input bound per output; includes bias exactly once."""
    w = np.asarray(weights, dtype=np.int64)
    max_input = max(abs(-128-input_zero_point), abs(127-input_zero_point))
    bound = max_input * np.sum(np.abs(w), axis=tuple(range(w.ndim-1)))
    bound += np.abs(np.asarray(bias, dtype=np.int64))
    if np.any(bound > I32_MAX):
        raise OverflowError("layer cannot guarantee INT32 accumulation")
    return bound.tolist()


def depthwise(x, weights, bias, spec):
    validate_int8(x)
    validate_int8(weights)
    if x.ndim != 4 or x.shape[0] != 1 or weights.ndim != 3 or x.shape[-1] != weights.shape[-1]:
        raise ValueError("expected NHWC batch1 and KH,KW,C weights")
    sh, sw = spec.get('stride', [1, 1])
    if sh <= 0 or sw <= 0:
        raise ValueError("positive stride required")
    _, h, w, c = x.shape
    kh, kw, _ = weights.shape
    if spec['padding'] == 'SAME':
        oh, ow = math.ceil(h/sh), math.ceil(w/sw)
        ph, pw = max((oh-1)*sh+kh-h, 0), max((ow-1)*sw+kw-w, 0)
        padded = np.pad(x.astype(np.int64), ((0,0),(ph//2,ph-ph//2),(pw//2,pw-pw//2),(0,0)),
                        constant_values=spec['input_zero_point'])
    elif spec['padding'] == 'VALID':
        oh, ow = (h-kh)//sh+1, (w-kw)//sw+1
        padded = x.astype(np.int64)
    else:
        raise ValueError("unknown padding")
    if oh <= 0 or ow <= 0:
        raise ValueError("empty convolution")
    accumulator_bound(weights, bias, spec['input_zero_point'])
    acc = np.broadcast_to(np.asarray(bias, dtype=np.int64), (1,oh,ow,c)).copy()
    for y in range(kh):
        for z in range(kw):
            window = padded[:,y:y+oh*sh:sh,z:z+ow*sw:sw,:]
            acc += (window-spec['input_zero_point']) * weights[y,z,:].astype(np.int64)
    return requantize(acc, spec)


def pw_accumulate(z, weights, ps, start, stop, input_zero_point):
    validate_int8(z)
    validate_int8(weights)
    if not 0 <= start < stop <= z.shape[-1] or weights.shape[0] != z.shape[-1]:
        raise ValueError("invalid contiguous channel prefix")
    result = np.asarray(ps, dtype=np.int64) + np.tensordot(
        z[...,start:stop].astype(np.int64)-input_zero_point,
        weights[start:stop].astype(np.int64), axes=([-1],[0]))
    if np.any(result < I32_MIN) or np.any(result > I32_MAX):
        raise OverflowError("partial sum overflow")
    return result.astype(np.int32)


def pointwise(z, weights, bias, spec):
    accumulator_bound(weights, bias, spec['input_zero_point'])
    ps = np.broadcast_to(bias, (*z.shape[:-1], weights.shape[-1])).copy().astype(np.int32)
    return requantize(pw_accumulate(z, weights, ps, 0, z.shape[-1], spec['input_zero_point']), spec)
