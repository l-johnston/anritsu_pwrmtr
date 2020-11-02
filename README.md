![Build Status](https://github.com/l-johnston/anritsu_pwrmtr/workflows/publish/badge.svg)
# `anritsu_pwrmtr`
Python interface to the Anritsu power meters

## Installation
```windows
>pip install anritsu_pwrmtr
```  

## Usage

For ML243xA models that use GPIB:

```python
>>> from anritsu_pwrmtr import CommChannel
>>> with CommChannel(13) as pm:
...     pm.ch1.read()
...
-10.1
```  
For MA243x0A models that use USB:

```python
>>> from anritsu_pwrmtr import CommChannel
>>> with CommChannel('<USB0::0x...::RAW>') as pm:
...     pm.read()
...
-10.1
```

Supported models:
- ML243xA
- MA243x0A

Supported features:
- Channel configuration for Readout mode
- Sensor calibration and zeroing
- Measuring power in Readout mode