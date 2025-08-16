from __future__ import annotations

import asyncio
import contextlib
import datetime
import html
import logging
from typing import TYPE_CHECKING, Final, cast

import aiohttp
from bs4 import BeautifulSoup
from typing_extensions import Self

from catholic_mass_readings import constants, models, utils

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import TracebackType

    from bs4.element import Tag

logger = logging.getLogger(__name__)


class USCCB:
    """Interface for querying the Daily Readings from https://bible.usccb.org/bible/readings/"""

    DEFAULT_MASS_TYPES: Final[list[models.MassType]] = [
        models.MassType.DAY,
        models.MassType.YEARA,
        models.MassType.YEARB,
        models.MassType.YEARC,
        models.MassType.DEFAULT,
    ]
    """Default list of MassTypes to try when searching for a mass on a given mass date."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: object,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        await self.close()
        return False

    async def close(self) -> Self:
        """Closes the underlying connection."""
        if self._session is None:
            return self
        await self._session.close()
        return self

    @staticmethod
    def today() -> datetime.date:
        """Gets today's date"""
        return datetime.datetime.now(tz=constants.DEFAULT_TIMEZONE).date()

    @staticmethod
    def max_query_date() -> datetime.date:
        """Gets latest date that can be queried"""
        today = USCCB.today()
        dt = datetime.date(today.year + 1, today.month, 1) + datetime.timedelta(days=31)
        return datetime.date(dt.year, dt.month, 1)

    @staticmethod
    def get_sunday_mass_dates(start: datetime.date, end: datetime.date | None = None) -> Iterable[datetime.date]:
        """Gets the list of Sunday mass dates from the next Sunday until `end` or `max_query_date`."""
        if end is not None and start >= end:
            msg = f"Invalid range ({start} >= {end})"
            raise ValueError(msg)

        weekday = start.weekday()
        if weekday != constants.SUNDAY_DAY_OF_WEEK:
            new_start = start + datetime.timedelta(days=constants.SUNDAY_DAY_OF_WEEK) - datetime.timedelta(days=weekday)
            if end is not None and end < new_start:
                # Incase the adjustment to start now means that end is before start, adjust end as well.
                end += new_start - start
            start = new_start

        return USCCB.get_mass_dates(start, end, datetime.timedelta(weeks=1))

    @staticmethod
    def get_mass_dates(
        start: datetime.date, end: datetime.date | None = None, step: datetime.timedelta = datetime.timedelta(weeks=1)
    ) -> Iterable[datetime.date]:
        """
        Gets the list of mass dates from the current date until
        `end` or `max_query_date` stepping by the `step` arg."""
        end = USCCB.max_query_date() if end is None else min(end, USCCB.max_query_date())
        if start >= end:
            msg = f"Invalid range ({start} >= {end})"
            raise ValueError(msg)

        dt = start
        while dt < end:
            yield dt
            dt += step

    async def get_today_mass(
        self,
        type_: models.MassType | None = None,
    ) -> models.Mass | None:
        """
        Gets the mass for today's date.

        Args:
            type_ (MassType): The type of Mass (if not specified,
                            then will select the first mass from DEFAULT_MASS_TYPES).

        Returns:
            Mass if retrieved from one of the MassTypes on the date.
        """
        today = self.today()
        if type_ is not None:
            return await self.get_mass(today, type_)
        return await self.get_mass_from_date(today)

    async def get_mass(
        self,
        date: datetime.date,
        type_: models.MassType,
    ) -> models.Mass | None:
        """Gets the mass for the date and type."""
        url = type_.to_url(date)
        return await self._get_mass(url, date, type_)

    async def get_mass_from_date(
        self, date: datetime.date, types: list[models.MassType] | None = None
    ) -> models.Mass | None:
        """
        Gets the first mass for the specified date and type.

        Args:
            date (datetime.date): The mass date.
            types (list[models.MassType]): The list of mass types to use (defaults to DEFAULT_MASS_TYPES)

        Returns:
            Mass if retrieved from one of the MassTypes on the date.
        """
        if types is None:
            types = self.DEFAULT_MASS_TYPES

        for type_ in types:
            url = type_.to_url(date)
            with contextlib.suppress(aiohttp.ClientResponseError):
                return await self._get_mass(url, date, type_)

        logger.warning("No mass for date: %s, types: %s", date, types)
        return None

    async def get_mass_from_url(self, url: str) -> models.Mass | None:
        """Gets the mass at the particular url."""
        date: datetime.date | None = None
        type_: models.MassType | str | None = None
        with contextlib.suppress(ValueError):
            parsed_url = utils.parse_url(url)
            if parsed_url:
                date = parsed_url[0]
                type_ = parsed_url[1]
                type_ = models.MassType(type_)

        return await self._get_mass(url, date, type_)

    async def get_mass_types(self, date: datetime.date) -> list[models.MassType]:
        """
        Gets the list of mass types for the specified date.

        Args:
            date (datetime.date): The mass date.

        Returns:
            list[models.MassType] for each of the supported mass types.
        """
        session = self._ensure_session()
        urls_to_type = {type_.to_url(date): type_ for type_ in models.MassType}
        requests = [session.head(url) for url in urls_to_type]
        responses = await asyncio.gather(*requests)
        ok_responses = (r for r in responses if r.ok)
        return sorted(urls_to_type[str(r.request_info.url)] for r in ok_responses)

    async def _get_mass(
        self, url: str, date: datetime.date | None, type_: models.MassType | str | None
    ) -> models.Mass | None:
        logger.debug("Querying url: %s", url)
        async with self._ensure_session().get(url, raise_for_status=True) as r:
            content = await r.text()

        logger.debug("Parsing content from url: %s", url)
        soup = BeautifulSoup(content, "html5lib")
        title = cast("Tag", soup.find("title"))
        sections: list[models.Section] = self._get_sections(soup)
        return models.Mass(date, type_, url, title.get_text(strip=True).split("|")[0].strip(), sections)

    def _get_sections(self, soup: BeautifulSoup) -> list[models.Section]:
        """Parses the Sections (Readings 1, 2, Gospel, Psalms, etc)."""
        sections: list[models.Section] = []
        prev_expects_children = False
        for container in utils.find_iter(soup, class_="container"):
            name = container.findChild(class_="name")
            address = cast("Tag", container.findChild(class_="address"))
            if not name or not address:
                continue

            verses = self._get_verses(address)
            if not verses:
                continue

            header = name.get_text(strip=True)
            type_ = models.SectionType.from_header(header)

            section: models.Section | None = None
            for reading in self._get_readings(container, verses):
                if section is None:
                    if m := constants.OR_PATTERN.match(reading.text):
                        expects_children = True
                        section = models.Section(type_, header, [reading.with_text(m.string[: m.start()].strip())])
                    else:
                        expects_children = False
                        section = models.Section(type_, header, [reading])
                else:
                    section = section.add_alternative(reading)

            if section is None:
                continue

            if sections and ((type_.is_unknown and prev_expects_children) or type_.is_alternative):
                sections[-1] = sections[-1].add_alternative(section.readings)
                prev_expects_children = False
                continue

            prev_expects_children = expects_children
            sections.append(section)

        return sections

    def _get_verses(self, parent: Tag) -> list[models.Verse]:
        """Gets the verses"""
        return list(map(self._create_verse, parent.findChildren(name="a", href=True)))

    def _create_verse(self, a: Tag) -> models.Verse:
        """Creates a verse from the specified Tag."""
        text = self._clean_text(a.get_text(strip=True))
        link = cast("str", a["href"]).strip()
        book_dict = utils.get_book_from_verse(link, text)
        book = book_dict["name"] if book_dict else None
        return models.Verse(text, link, book)

    def _get_readings(self, container: Tag, verses: list[models.Verse]) -> Iterable[models.Reading]:
        content_body = cast("Tag", container.findChild(class_="content-body"))
        empty = True
        for v, lines in self._get_raw_readings(content_body, verses):
            text = self._clean_text("".join(lines)).strip()
            if text:
                yield models.Reading(v, text)
                empty = False

        if empty:
            yield models.Reading(verses, self._clean_text(content_body.get_text(strip=True, separator="\n")).strip())

    def _get_raw_readings(
        self, content_body: Tag, verses: list[models.Verse]
    ) -> Iterable[tuple[list[models.Verse], list[str]]]:
        lines: list[str] = []
        paragraph: Tag
        for paragraph in content_body.find_all("p"):
            txt = paragraph.get_text(
                strip=False,
            )
            if constants.OR_PATTERN.match(txt.strip()):
                yield (verses, lines)
                lines = []
                verses = []
                continue

            curr_verses = self._get_verses(paragraph)
            if curr_verses:
                yield (verses, lines)
                lines = []
                verses = curr_verses
                continue

            lines.append(txt)

        yield (verses, lines)

    @staticmethod
    def _clean_text(string: str) -> str:
        return html.unescape(string.replace("\xa0", " "))

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = self._create_session()
        return self._session

    def _create_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        )
