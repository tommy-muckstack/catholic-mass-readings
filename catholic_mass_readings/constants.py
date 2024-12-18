import datetime
import re
from typing import Final

import pytz

SUNDAY_DAY_OF_WEEK: Final[int] = 6

DATE_FMT: Final[str] = "%m%d%y"

OR_PATTERN: Final[re.Pattern] = re.compile("OR[:]?$", re.IGNORECASE)

DEFAULT_TIMEZONE: Final[datetime.tzinfo] = pytz.timezone("America/New_York")
