# catholic-mass-readings

[![CI Build](https://github.com/rcolfin/catholic-mass-readings/actions/workflows/ci.yml/badge.svg)](https://github.com/rcolfin/catholic-mass-readings/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/rcolfin/catholic-mass-readings.svg)](https://github.com/rcolfin/catholic-mass-readings/blob/main/LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/catholic-mass-readings)](https://pypi.python.org/pypi/catholic-mass-readings)
[![versions](https://img.shields.io/pypi/pyversions/catholic-mass-readings.svg)](https://github.com/rcolfin/catholic-mass-readings)

Provides an API for scraping the web page from [Daily Readings](https://bible.usccb.org/bible/readings/) website of United States Conference of Catholic Bishops.

## Development

### Setup Python Environment:

Run [scripts/console.sh](../scripts/console.sh) uv install

The first time run

```sh
uvx pre-commit install
```

### If you need to relock:

Run [scripts/lock.sh](../scripts/lock.sh)

### Run code

Run [scripts/console.sh](../scripts/console.sh) uv run python -m catholic_mass_readings


## API Usage

### HTTP service (Railway / FastAPI)

The repository includes a FastAPI wrapper (`main.py`) that powers the Railway
deployment. Once it's running, you can fetch readings by calling the `/readings`
endpoint:

```
GET https://<your-railway-host>/readings?date=2025-09-24
```

The JSON mirrors Credo Chat's `DailyReading` model, including fields such as
`firstReading`, `responsorialPsalm`, `secondReading`, and `gospel`. Use
`/readings/today` for the current day or `/readings/{date}/alternates` to fetch
optional memorial readings.

### Python API

```python
import asyncio
import datetime

from catholic_mass_readings import USCCB, models

# To get a mass for a particular date:
async with USCCB() as usccb:
    mass = await usccb.get_mass(datetime.date(2024, 12, 25), models.MassType.VIGIL)
    print(mass)

# To query for a range of Sunday masses:
async with USCCB() as usccb:
    dates = usccb.get_sunday_mass_dates(datetime.date(2024, 12, 25), datetime.date(2025, 1, 25))
    tasks = [usccb.get_mass_from_date(dt, types) for dt in dates]
    responses = await asyncio.gather(*tasks)
    masses = [m for m in responses if m]
    masses.sort(key=lambda m: m.date.toordinal() if m.date else -1)
    for mass in masses:
        end = "\n" if mass is masses[-1] else "\n\n"
        print(mass, end=end)

# To query for a range of masses (step how you want to):
async with USCCB() as usccb:
    dates = usccb.get_mass_dates(datetime.date(2024, 12, 25), datetime.date(2025, 1, 25), step=datetime.timedelta(days=1))
    tasks = [usccb.get_mass_from_date(dt) for dt in dates]
    responses = await asyncio.gather(*tasks)
    masses = [m for m in responses if m]
    masses.sort(key=lambda m: m.date.toordinal() if m.date else -1)
    for mass in masses:
        end = "\n" if mass is masses[-1] else "\n\n"
        print(mass, end=end)

# To query for a list of all the mass types on a particular date:
async with USCCB() as usccb:
    mass_types = await usccb.get_mass_types(datetime.date(2024, 12, 25))
    for mass_type in mass_types:
        print(mass_type.name)
```

As a CLI

```sh
# To get a mass for a particular date:
python -m catholic_mass_readings get-mass --date 2024-12-25 --type vigil

# To query for a range of Sunday masses:
python -m catholic_mass_readings get-sunday-mass-range --start 2024-12-25 --end 2025-01-01

# To query for a range of masses (step how you want to):
python -m catholic_mass_readings get-mass-range --start 2024-12-25 --end 2025-01-01 --step 7

# To query for a list of mass types on a particular date:
python -m catholic_mass_readings get-mass-types --date 2025-12-25

# or saving to a file...

# To get a mass for a particular date:
python -m catholic_mass_readings get-mass --date 2024-12-25 --type vigil --save mass.json

# To query for a range of Sunday masses:
python -m catholic_mass_readings get-sunday-mass-range --start 2024-12-25 --end 2025-01-01 --save mass.json

# To query for a range of masses (step how you want to):
python -m catholic_mass_readings get-mass-range --start 2024-12-25 --end 2025-01-01 --step 7 --save mass.json
```

## Installation

To install catholic-mass-readings from PyPI, use the following command:

    $ pip install catholic-mass-readings

You can also clone the repo and run the following command in the project root to install the source code as editable:

    $ pip install -e .

## Documentation
The documentation for `catholic-mass-readings` can be found [here](https://rcolfin.github.io/catholic-mass-readings/) or in the project's docstrings.
