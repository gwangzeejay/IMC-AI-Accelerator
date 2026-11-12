# Long-Term Tracing of Indoor Solar Harvesting


## Dataset Information

This dataset presents long-term term indoor solar harvesting traces and jointly monitored with the ambient conditions. The data is recorded at 6 indoor positions with diverse characteristics at our institute at ETH Zurich in Zurich, Switzerland.

The data is collected with a measurement platform [3] consisting of a solar panel (AM-5412) connected to a bq25505 energy harvesting chip that stores the harvested energy in a virtual battery circuit. Two TSL45315 light sensors placed on opposite sides of the solar panel monitor the illuminance level and a BME280 sensor logs ambient conditions like temperature, humidity and air pressure.

The dataset contains the measurement of the energy flow at the input and the output of the bq25505 harvesting circuit, as well as the illuminance, temperature, humidity and air pressure measurements of the ambient sensors. The following timestamped data columns are available in the raw measurement format, as well as preprocessed and filtered HDF5 datasets:

* `V_in` - Converter input/solar panel output voltage, in volt
* `I_in` - Converter input/solar panel output current, in ampere
* `V_bat` - Battery voltage (emulated through circuit), in volt
* `I_bat` - Net Battery current, in/out flowing current, in ampere
* `Ev_left` - Illuminance left of solar panel, in lux
* `Ev_right` - Illuminance left of solar panel, in lux
* `P_amb` - Ambient air pressure, in pascal
* `RH_amb` - Ambient relative humidity, unit-less between 0 and 1
* `T_amb` - Ambient temperature, in centigrade Celsius

The following publication presents and overview of the dataset and more details on the deployment used for data collection. A copy of the abstract is included in this dataset, see the file [`abstract.pdf`](abstract.pdf).

> L. Sigrist, A. Gomez, and L. Thiele.
> *Dataset: Tracing Indoor Solar Harvesting*.
> In Proceedings of the 2nd Workshop on Data Acquisition To Analysis (DATA '19), 2019.


## Folder Structure and Files

* [`processed/`](processed) - This folder holds the imported, merged and filtered datasets of the power and sensor measurements. The datasets are stored in HDF5 format and split by measurement position `posXX` and and power and ambient sensor measurements. The files belonging to this folder are contained in archives named `yyyy_mm_processed.tar`, where `yyyy` and `mm` represent the year and month the data was published. A separate file lists the exact content of each archive (see below).
* [`raw/`](raw) - This folder holds the raw measurement files recorded with the RocketLogger [1, 2] and using the measurement platform available at [3]. The files belonging to this folder are contained in archives named `yyyy_mm_raw.tar`, where `yyyy` and `mm` represent the year and month the data was published. A separate file lists the exact content of each archive (see below).
* [`LICENSE`](LICENSE) - License information for the dataset.
* [`README.md`](README.md) - The README file containing this information.
* [`abstract.pdf`](abstract.pdf) - A copy of the above mentioned abstract submitted to the DATA '19 Workshop, introducing this dataset and the deployment used to collect it.
* [`raw_import.ipynb`](raw_import.ipynb) [[open in nbviewer](https://nbviewer.jupyter.org/urls/zenodo.org/record/3715472/files/raw_import.ipynb)] - Jupyter Python notebook to import, merge, and filter the raw dataset from the `raw/` folder. This is the exact code used to generate the processed dataset and store it in the HDF5 format in the `processed/` folder.
* [`raw_preview.ipynb`](raw_preview.ipynb) [[open in nbviewer](https://nbviewer.jupyter.org/urls/zenodo.org/record/3715472/files/raw_preview.ipynb)] - This Jupyter Python notebook imports the raw dataset directly and plots a preview of the full power trace for all measurement positions.
* [`processing_python.ipynb`](processing_python.ipynb) [[open in nbviewer](https://nbviewer.jupyter.org/urls/zenodo.org/record/3715472/files/processing_python.ipynb)] - Jupyter Python notebook demonstrating the import and use of the processed dataset in Python. Calculates column-wise statistics, includes more detailed power plots and the simple energy predictor performance comparison included in the abstract.
* [`processing_r.ipynb`](processing_r.ipynb) [[open in nbviewer](https://nbviewer.jupyter.org/urls/zenodo.org/record/3715472/files/processing_r.ipynb)] - Jupyter R notebook demonstrating the import and use of the processed dataset in R. Calculates column-wise statistics and extracts and plots the energy harvesting conversion efficiency included in the abstract. Furthermore, the harvested power is analyzed as a function of the ambient light level.


## Dataset File Lists

#### Processed Dataset Files

The list of the processed datasets included in the `yyyy_mm_processed.tar` archive is provided in `yyyy_mm_processed.files.md`.
The markdown formatted table lists the name of all files, their size in bytes, as well as the SHA-256 sums.

For reference, the list was generated using the command below. Be aware that recreating this list requires complete reading of all files and takes a while.
```bash
{ echo -e "| Filename \t| Size (Bytes) \t| SHA-256 Sum \t|\n| :--- \t| ---: \t| :--- \t|";
  find "./processed/" -type f -printf '%s\t' -exec sha256sum {} \; | awk '{ print "| " $3 "\t| " $1 "\t| " $2 "\t|" }' | sort;
} | column -t -s $'\t' > processed.files.md
```

#### Raw Dataset Files

A list of the raw measurement files included in the `yyyy_mm_raw.tar` archive(s) is provided in `yyyy_mm_raw.files.md`.
The markdown formatted table lists the name of all files, their size in bytes, as well as the SHA-256 sums.

For reference, the list was generated using the command below. Be aware that recreating this list requires complete reading of all files and takes a while.
```bash
{ echo -e "| Filename \t| Size (Bytes) \t| SHA-256 Sum \t|\n| :--- \t| ---: \t| :--- \t|";
  find "./raw/" -type f -printf '%s\t' -exec sha256sum {} \; | awk '{ print "| " $3 "\t| " $1 "\t| " $2 "\t|" }' | sort;
} | column -t -s $'\t' > raw.files.md
```


## Dataset Revisions

### v1.0 (2019-08-03)

Initial release.
Includes the data collected from 2017-07-27 to 2019-08-01.
The dataset archive files related to this revision are `2019_08_raw.tar` and `2019_08_processed.tar`.
For position *pos06*, the measurements from 2018-01-06 00:00:00 to 2018-01-10 00:00:00 are filtered (data inconsistency in file `indoor1_p27.rld`).

### v1.1 (2019-09-09)

Revision of the processed dataset v1.0 and addition of the final dataset abstract.
Updated processing scripts reduce the timestamp drift in the processed dataset, the archive `2019_08_processed.tar` has been replaced.
For position *pos06*, the measurements from 2018-01-06 16:00:00 to 2018-01-10 00:00:00 are filtered (`indoor1_p27.rld` data inconsistency).

### v2.0 (2020-03-20)

Addition of new data.
Includes the raw data collected from 2019-08-01 to 2019-03-16. The processed data is updated with full coverage from 2017-07-27 to 2019-03-16.
The dataset archive files related to this revision are `2020_03_raw.tar` and `2020_03_processed.tar`.


## Dataset Authors, Copyright and License

* Authors: Lukas Sigrist, Andres Gomez, and Lothar Thiele
* Contact: Lukas Sigrist (<lukas.sigrist@tik.ee.ethz.ch>)
* Copyright: (c) 2017-2020, ETH Zurich, Computer Engineering Group
* License: Creative Commons Attribution 4.0 International License (<https://creativecommons.org/licenses/by/4.0/>)


## References

[1] L. Sigrist, A. Gomez, R. Lim, S. Lippuner, M. Leubin, and L. Thiele. *Measurement
and validation of energy harvesting IoT devices.* In Design, Automation & Test in
Europe Conference & Exhibition (DATE), 2017.

[2] ETH Zurich, Computer Engineering Group. RocketLogger Project Website, <https://rocketlogger.ethz.ch/>.

[3] L. Sigrist. *Solar Harvesting and Ambient Tracing Platform*, 2019. <https://gitlab.ethz.ch/tec/public/employees/sigristl/harvesting_tracing>
