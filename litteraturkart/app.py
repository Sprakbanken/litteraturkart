# %%
import logging

import folium
import pandas as pd
import streamlit as st
import streamlit_folium

try:
    from litteraturkart import utils
except ModuleNotFoundError:
    import utils


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# %%
@st.cache_data
def load_corpus() -> pd.DataFrame:
    """Fetch metadata from 19th century literature corpus."""
    logging.info("Loading corpus")
    corpus = utils.get_imag_corpus()
    return corpus


@st.cache_data
def fetch_locations(docid) -> dict:
    """Fetch locations from the corpus."""
    logging.info("Fetching locations")
    locations = utils.geo_locations(docid)
    # locations = utils.many_geo_locations(docids)
    return locations

def download_locations(locations: pd.DataFrame) -> None:
    """Download locations as an Excel file."""
    logging.info("Downloading locations")
    data = utils.to_excel(locations)
    return data


# %%
def main():
    """Main function for the app."""
    ### HEADER
    st.set_page_config(
        page_title="Litteraturkart",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "About": "App for å plotte stedsnavn fra 1800-tallslitteratur på kart. Laget av [DH-laben](https://www.nb.no/dh-lab/) ved Nasjonalbiblioteket for [ImagiNation-prosjektet](https://www.ntnu.edu/isl/imagination).",
        },
    )

    st.title("ImagiNation Demokart")

    ### SETTINGS

    settings = st.expander("Innstillinger")
    corpus = load_corpus()

    settings.write("### Filtrer tekstutvalg")
    settings.write(f"Totalt antall publikasjoner i korpuset: **{corpus.shape[0]}**")
    subcorpus = utils.corpus_parameters(corpus, settings)
    docid = subcorpus.dhlabid.values[0]

    # %%
    settings.write("### Kartvisning")
    mapfilter1, mapfilter2, _ = settings.columns([2, 4, 2])
    freq_lim = mapfilter1.number_input(
        "Sett nedre frekvensgrense",
        min_value=1,
        value=1,
        help="Filtrer visningen av stedsnavn på hvor ofte de færreste forekommer i teksten.",
    )
    filnavn = mapfilter2.text_input(
        "Filnavn for nedlasting",
        # f"stedsnavn_{utils.format_filename(title)}.xlsx",
        f"stedsnavn_dhlabid-{docid}.xlsx",
        help="Navn på nedlastbar Excel-fil med stedsnavnene.",
    )
    # selected_features = mapfilter2.multiselect(
    #    "Velg kode for stedstyper",
    #    utils.feature_codes,
    #    [],  # ["CONT", "PCLI", "PPLC"],
    #    format_func=utils.format_func_code,
    #    help='Velg hvilke "feature codes" fra geonames som skal inkluderes på kartet (finkornete kategorier)',
    # )
    col1, col2, col3 = st.columns([3,1, 22])
    update_map = col1.button(
        "Oppdater kartet",
        help="Plott steder på kartet, og oppdater kartet med nye innstillinger."
    )
    # %%%

    ### PLOT MAP

    # Initialise a Folium map at a global scale
    m = folium.Map(location=[0, 0], zoom_start=2)

    # %%
    if update_map:
        # %%
        locations = fetch_locations(docid)
        # %%
        if locations.empty:
            col3.write("Ingen stedsnavn å vise fra den valgte tittelen. Prøv en annen tittel.")
        else:

            col3.write(f"Viser {locations.shape[0]} stedsnavn. ")
            filebutton = col2.download_button(
                ":arrow_down:",
                utils.to_excel(locations),
                filnavn,
                help="Last ned stedsnavnene i excelformat. Åpnes i Excel eller tilsvarende.",
            )

            if filebutton:
                pass
            for i, row in locations.iterrows():
                if row["frekv"] < freq_lim:
                    continue
                try:
                    urn = subcorpus.loc[subcorpus.dhlabid == row["dhlabid"], "urn"].values
                    pin = utils.create_map_pin(row, urn)
                    pin.add_to(m)
                except IndexError:
                    st.warning("Kunne ikke plotte stedsnavn")
                    logging.warning(f"IndexError: {row}")
                    continue
            streamlit_folium.folium_static(m, height=800, width=1200)
        # Save the map to an HTML file
        # map_file = "map.html"
        # m.save(map_file)
        # Open the map in a new tab
        # webbrowser.open("file://" + os.path.realpath(map_file), new=2)


if __name__ == "__main__":
    main()
