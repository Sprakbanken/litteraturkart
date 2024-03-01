# %%
import re
import json
import logging
from typing import Iterable

import dhlab as dh
import folium
import pandas as pd
import pyarrow as pa
import requests
from langcodes import Language
from io import BytesIO
from string import punctuation

from litteraturkart.feature_values import (
    feature_classes, feature_codes, feature_colour_map)


def format_filename(full_title: str) -> str:
    """Replace punctuation and whitespace in a string with hyphens."""
    # Split main title and subtitle
    title = full_title.split(":")[0].strip()
    return "-".join(re.sub("[" + punctuation + "]", "", title).split())


def imag_corpus():
    logging.info("fetching corpus metadata from dhlab API")
    res = requests.get(f"{dh.constants.BASE_URL}/imagination/all")
    if res.status_code == 200:
        pa_tab = pa.Table.from_pylist(res.json())
        df = pa_tab.to_pandas(types_mapper=pd.ArrowDtype)
    else:
        df = pd.DataFrame()
    return df


def get_imag_corpus():
    """Fetch the full collection of ImagiNation corpus metadata and wrap it in a dataframe."""
    logging.info("creating corpus object from metadata")
    im = imag_corpus()
    c = dh.Corpus()
    c.extend_from_identifiers(im.urn)
    corpus = c.frame
    corpus.dhlabid = corpus.dhlabid.astype(int)
    corpus = corpus[
        [
            "urn",
            "dhlabid",
            "title",
            "authors",
            "city",
            "year",
            "publisher",
            "langs",
            "subjects",
            "ddc",
            "genres",
            "literaryform",
            "doctype",
            "ocr_creator",
        ]
    ]
    corpus = corpus.merge(im[["urn", "category"]], left_on="urn", right_on="urn")
    corpus["metatitle"] = corpus.apply(combine_title_info, axis=1)
    return corpus

# %%
def geo_locations(dhlabid):
    """Fetch geolocation info for placenames in a given publication."""
    res = requests.get(
        f"{dh.constants.BASE_URL}/imagination_geo_data", params={"dhlabid": dhlabid}
    )
    # if res.status_code == 200:

    try:
        res.raise_for_status()
        data = pd.DataFrame.from_dict(res.json()).convert_dtypes(dtype_backend='pyarrow')
    except requests.exceptions.RequestException as e:
        print(e)
        data = pd.DataFrame()
    # else:

    return data

# %%
def load_corpus_csv(filename: str):
    c = dh.Corpus.from_csv(filename)
    corpus = c.frame
    corpus.year = corpus.year.astype(int)
    return corpus


def read_jsonl(filename: str):
    with open(filename) as f:
        jsonlines = [json.loads(line) for line in f.readlines() if line]
    return jsonlines


def to_excel(df):
    """Make an excel object out of a dataframe as an IO-object.

    Copied function from https://github.com/NationalLibraryOfNorway/dhlab-app-corpus/blob/main/app/app.py
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Stedsnavn")
    processed_data = output.getvalue()
    return processed_data


# Input options formatting
def format_func_class(option):
    return option + " – " + feature_classes[option]


def format_func_code(option):
    return option + " – " + feature_codes[option]


def format_single_author(author: str) -> str:
    """Format author name as <first name> <last name>."""
    names = author.split(",")
    if len(names) > 1:
        fullname = names[1].strip() + " " + names[0].strip()
    else:
        fullname = names[0].strip()
    return fullname


def format_author(option: str) -> str:
    """Format a string with author name(s) as 'first1 last1, first2 last2, ...'

    Split string on '/' delimiter and call `format_single_author` on each name.
    """
    return ", ".join(format_single_author(auth) for auth in option.split("/"))


def format_title(title: str, authors: str = None, year: int = None) -> str:
    """Format a title as 'AUTHOR : TITLE (YEAR)'."""
    author_name = f"{format_author(authors)} : " if authors else ""
    publication_year = f" ({int(year)})" if year else ""
    credited_title = author_name + f'"{title}"' + publication_year
    return credited_title


def format_language(option: str) -> str:
    """Format language codes with their full name (in English)."""
    return Language.get(option).display_name()


def to_csv(data: pd.DataFrame):
    return data.to_csv()


# DATA WRANGLING
def extract_unique_values(data: pd.Series, sep: str = "/") -> list:
    """Format a list of unique values from a multivalue string from a pandas Series."""
    return sorted(
        list(
            {
                unit.strip()
                for item in data.unique()
                if isinstance(item, str)
                for unit in item.split(sep)
                if unit
            }
        )
    )


def bool_filter(data: pd.Series, examples: Iterable, regex=True) -> pd.Series:
    """Filter a pandas Series with a list of examples."""
    if regex:
        regpat = regpat = (
            ("|".join(examples) if examples else "")
            .replace("(", "\(")
            .replace(")", "\)")
        )
        boolean_series = data.str.contains(regpat, regex=True)
    else:
        try:
            examples_exist = examples.any()
        except AttributeError:
            examples_exist = bool(examples)
        boolean_series = data.isin(examples if examples_exist else data)
    return boolean_series


def filtered_selection(
    meta_df: pd.DataFrame,
    # selection_col: Union[list, str] = "dhlabid",
    docids: Iterable = None,
    categories: Iterable = None,
    titles: Iterable = None,
    authors: Iterable = None,
    from_year: int = 1814,
    to_year: int = 1905,
    languages: Iterable = None,
    publishers: Iterable = None,
    places: Iterable = None,
) -> pd.Series:
    """Reduce the available selection_col column values from the corpus,
    given the other chosen metadata parameters.
    dhlabid,urn,authors,year,langs,title
    """
    doc_sel = bool_filter(meta_df["dhlabid"], docids, regex=False)
    cat_sel = bool_filter(meta_df["category"], categories)
    auth_sel = bool_filter(meta_df["authors"], authors)
    title_sel = bool_filter(
        meta_df["title"], titles, regex=False
    )
    # publisher_sel = bool_filter(meta_df["publisher"], publishers)
    # place_sel = bool_filter(meta_df["place"], places)
    lang_sel = bool_filter(meta_df["langs"], languages)
    period = (from_year - 1 < meta_df["year"]) & (meta_df["year"] < to_year + 1)

    # selection = meta_df[selection_col][
    selection = meta_df[
        doc_sel
        & cat_sel
        & auth_sel
        & title_sel
        # & publisher_sel & place_sel
        & lang_sel
        & period
    ]
    return selection if not selection.empty else meta_df  # [selection_col]


def filter_unique_options(df, col, **kwargs):
    subcorpus = filtered_selection(df, kwargs)
    return extract_unique_values(subcorpus[col])

def combine_title_info(row) -> list:
    """Combine title, author and year into a single string."""
    # row = corpus.loc[corpus.dhlabid == dhlabid]
    return format_title(row["title"], row["authors"], row["year"])


def corpus_parameters(metadata, param_box):
    """Streamlit widget to filter the corpus with metadata parameters.

    Args:
        metadata: pd.DataFrame
        param_box: A streamlit container, expander or similar, to insert the input widgets into
    """

    filter1, filter2 = param_box.columns([6, 4], gap="large")

    chosen_categories = filter1.multiselect(
        label="Tekstkategori",
        options=metadata.category.unique(),
        placeholder="Velg en kategori",
    )

    from_year, to_year = filter2.slider(
        label="Publikasjonsår", min_value=1814, max_value=1905, value=(1814, 1905)
    )

    chosen_authors = filter1.multiselect(
        "Forfatter",
        extract_unique_values(metadata["authors"]),
        [],
        placeholder="Velg en forfatter",
        format_func=format_author,
        help="Velg forfattere å filtrere utvalget på.",
    )

    chosen_language = filter2.multiselect(
        "Språk",
        extract_unique_values(metadata["langs"]),
        [],
        format_func=format_language,
        placeholder="Velg språk",
        help="Velg språk for publikasjonene.",
    )
    # %%
    subcorpus = filtered_selection(
        metadata,
        # selection_col="dhlabid",
        categories=chosen_categories,
        authors=chosen_authors,
        languages=chosen_language,
        from_year=from_year,
        to_year=to_year,
    )

    chosen_title = filter1.selectbox(
        "Tittel",
        subcorpus["metatitle"],
        placeholder='Amalie Skram : "Samlede værker . 2-4 2 : Hellemyrsfolket Sjur Gabriel ; To venner" (1905)',
        #placeholder="Velg en tittel",
        disabled=False,
        help=f"Velg 1 av {subcorpus.shape[0]} titler å plotte stedsnavn fra på kartet.",
    )
    subcorpus = metadata[metadata.metatitle == chosen_title]
    filter2.write(f"dhlabid for valgt tittel: `{subcorpus.dhlabid.values[0]}`")
    return subcorpus


def create_map_pin(row: pd.Series, urn: str):
    """Create an html string for a folium map pin popup."""
    # feature_code = row.feature_code
    feature_class = row.feature_class
    html = f"""
    <h4>{row['token']} <em>{row['name']}</em></h4>
    <p> Frekvens: {row['frekv']}</p>
    <p><a href=https://www.nb.no/search?q={row.token}&mediatype=b%C3%B8ker&fromDate=18140101&toDate=19051231 target='_blank'> {row.token} fra 1814 til 1905</a></p>
    <p><a href=https://www.nb.no/items/{urn}?searchText={row.token} target='_blank'>{row.token} i teksten</a></p>"""

    iframe = folium.IFrame(html=html, width=200, height=200)
    popup_frame = folium.Popup(iframe, max_width=2600)
    # pin_size = 20 + row.frekv
    return folium.Marker(
        location=(row.latitude, row.longitude),
        icon=folium.Icon(
            color=feature_colour_map.get(feature_class, "blue"),
            icon="drop",
            prefix="fa",
        ),
        popup=popup_frame,
    )

# %%
