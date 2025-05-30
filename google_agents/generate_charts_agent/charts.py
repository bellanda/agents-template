import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

import plotly.express as px

BASE_DIR = pathlib.Path(__file__).parent.parent.parent


def generate_example_plot():
    """
    Função para retornar um exemplo de plot.
    """

    data_canada = px.data.gapminder().query("country == 'Canada'")
    fig = px.bar(data_canada, x="year", y="pop")
    fig.write_image(BASE_DIR / "data" / "server" / "example_plot.jpg")

    return {
        "markdown_to_show_image": "![Plot](http://localhost:8005/download_file?file_name=example_plot.jpg)",
    }
