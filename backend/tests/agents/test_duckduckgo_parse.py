"""duckpy was replaced by an in-house parser (wave U5); lock the HTML contract the web search relies on."""

from agents.web_search_agent.core.duckduckgo import parse_results

PAGE = """
<div class="links_main"><a class="badge--ad">Ad</a><h2><a>Ad title</a></h2>
  <a class="result__snippet">ad</a><a class="result__url" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fad.example">x</a></div>
<div class="links_main"><h2><a> Real title </a></h2>
  <a class="result__snippet"> Real snippet </a>
  <a class="result__url" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa%3Fb%3D1&amp;rut=abc">x</a></div>
<div class="links_main"><h2><a>No snippet</a></h2><a class="result__url" href="/x">x</a></div>
"""


def test_parse_results_skips_ads_and_malformed_and_unwraps_urls():
    assert parse_results(PAGE) == [
        {"url": "https://example.com/a?b=1", "title": "Real title", "description": "Real snippet"}
    ]
