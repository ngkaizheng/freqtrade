"""Reachability probe for candidate hosts."""
import concurrent.futures as cf
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}
HOSTS = [
    "https://insights.deribit.com/",
    "https://insights.glassnode.com/the-basis-trade-is-alive-and-well",
    "https://a16zcrypto.com/",
    "https://www.bis.org/publ/qtrpdf/r_qt2212.htm",
    "https://www.fsb.org/2022/07/the-financial-stability-implications-of-digital-assets/",
    "https://www.iosco.org/library/pubdocs/pdf/IOSCOPD688.pdf",
    "https://www.esma.europa.eu/press-news/esma-news/esma-publishes-final-guidelines-mica",
    "https://www.federalreserve.gov/newsevents/pressreleases/enforcement20201019a.htm",
    "https://www.cftc.gov/PressRoom/PressReleases/8482-22",
    "https://www.coindesk.com/",
    "https://www.theblock.co/",
    "https://coinmetrics.io/",
    "https://charts.coinmetrics.io/",
    "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3760048",
    "https://www.ey.com/en_us/insights/crypto",
    "https://www.galaxy.com/insights/research",
    "https://research.kaiko.com/insights",
    "https://blog.kaiko.com/",
    "https://www.algorithmictradingpodcast.com/",
    "https://www.paradigm.xyz/",
    "https://r.jina.ai/https://insights.glassnode.com/the-basis-trade-is-alive-and-well",
    "https://www.sec.gov/newsroom/press-releases/2022-78",
    "https://eur-lex.europa.eu/eli/reg/2023/1114/oj",
    "https://www.binance.com/en/support/faq/detail/360033525031",
]


def probe(u):
    try:
        r = requests.get(u, headers=UA, timeout=25, allow_redirects=True)
        return u, r.status_code, len(r.text)
    except Exception as e:  # noqa: BLE001
        return u, "EXC", str(e)[:80]


with cf.ThreadPoolExecutor(max_workers=10) as ex:
    for u, s, n in ex.map(probe, HOSTS):
        print(f"{s:>6} {str(n):>9}  {u}")
