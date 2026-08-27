"""
╔══════════════════════════════════════════════════════════════════════╗
║  AGENTE 1 — PUBMED SCRAPER v2.0                                    ║
║  piediabetico.lat                                                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  Fuentes configuradas:                                              ║
║    1. PubMed / NCBI Entrez (API pública, sin clave)                ║
║    2. IWGDF Guidelines (iwgdfguidelines.org)                        ║
║    3. JDFC Journal (jdfc.org — acceso abierto)                     ║
║    4. Diabetic Foot & Ankle (diabeticfootandankle.net)             ║
║    5. WoundSource (woundsource.com — últimas noticias)             ║
║    6. Wound Care Weekly (woundcareweekly.com)                      ║
║                                                                     ║
║  Corre automáticamente cada sábado a las 23hs via Celery Beat      ║
║  Guarda resultados en: /workspace/scratch/raw_articles.json        ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)


class PubMedScraperAgent:
    """
    Agente 1 — Rastreador multicuente de literatura científica sobre pie diabético.
    
    Busca en PubMed + fuentes especializadas y consolida los artículos
    de la semana en un JSON unificado para que el Agente 2 (Redactor) los procese.
    """

    # ── PubMed API ────────────────────────────────────────────────
    BASE_URL_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    BASE_URL_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    # ── Queries MeSH para PubMed ──────────────────────────────────
    QUERIES_PUBMED = [
        # Guías clínicas y revisiones sistemáticas
        (
            '("Diabetic Foot"[Mesh] OR "Foot Ulcer"[Mesh]) AND '
            '("Practice Guideline"[Publication Type] OR '
            '"Systematic Review"[Publication Type] OR '
            '"Meta-Analysis"[Publication Type])',
            5
        ),
        # Infección y antibióticos
        (
            '("Diabetic Foot"[Mesh] OR "Foot Ulcer, Diabetic"[Mesh]) AND '
            '("Anti-Bacterial Agents"[Mesh] OR "Osteomyelitis"[Mesh] OR '
            '"Wound Infection"[Mesh])',
            3
        ),
        # Cicatrización y apósitos
        (
            '("Wound Healing"[Mesh] AND "Diabetic Foot"[Mesh]) AND '
            '("Bandages"[Mesh] OR "Wound Closure Techniques"[Mesh] OR '
            '"Debridement"[Mesh])',
            3
        ),
        # Off-loading y biomecánica
        (
            '("Diabetic Foot"[Mesh]) AND '
            '("Orthopedic Equipment"[Mesh] OR "Biomechanical Phenomena"[Mesh] OR '
            '"Weight-Bearing"[Mesh])',
            2
        ),
    ]

    # ── Fuentes web especializadas ─────────────────────────────────
    FUENTES_WEB = [
        {
            "nombre": "IWGDF Guidelines",
            "url": "https://iwgdfguidelines.org/guidelines/",
            "tipo": "iwgdf",
        },
        {
            "nombre": "Journal of Diabetic Foot Complications",
            "url": "https://jdfc.org/",
            "tipo": "jdfc",
        },
        {
            "nombre": "Diabetic Foot & Ankle",
            "url": "https://www.tandfonline.com/journals/zdfa20",
            "tipo": "generic",
        },
        {
            "nombre": "WoundSource",
            "url": "https://www.woundsource.com/blog",
            "tipo": "generic",
        },
        {
            "nombre": "Wound Care Weekly",
            "url": "https://woundcareweekly.com/",
            "tipo": "generic",
        },
    ]

    # ── Artículos de respaldo (fallback offline) ───────────────────
    MOCK_ARTICLES = [
        {
            "pmid": "38291034",
            "fuente": "PubMed",
            "title": "IWGDF Guidelines on the prevention and management of diabetes-related foot disease (2023 Edition)",
            "authors": "Bus, Sicco A.; Lavery, Lawrence A.; et al.",
            "journal": "Diabetes/Metabolism Research and Reviews",
            "pub_date": "2023-11",
            "doi": "10.1002/dmrr.3697",
            "url": "https://pubmed.ncbi.nlm.nih.gov/38291034/",
            "abstract_raw": (
                "**BACKGROUND:** Diabetes-related foot disease remains a major global health challenge. "
                "These guidelines present the 2023 updates of the IWGDF on prevention, off-loading, "
                "infection, peripheral artery disease, and wound healing.\n\n"
                "**RECOMMENDATIONS:** Integrated foot care (at-risk screening, education, protective "
                "footwear) is strongly recommended. Active off-loading (non-removable knee-high devices) "
                "is the gold standard for neuropathic plantar ulcers."
            ),
            "scraped_at": datetime.now().isoformat(),
        },
        {
            "pmid": "37582049",
            "fuente": "PubMed",
            "title": "External validation of Meggitt-Wagner, Texas University, SINBAD, and Saint Elian classifications",
            "authors": "Ochoa-Ruz, J. L.; Alvarado-Vásquez, N.; et al.",
            "journal": "PLOS One",
            "pub_date": "2024-06",
            "doi": "10.1371/journal.pone.0284901",
            "url": "https://pubmed.ncbi.nlm.nih.gov/37582049/",
            "abstract_raw": (
                "**RESULTS:** The Saint Elian classification system (SEWSS) demonstrated the highest "
                "sensitivity (91.2%) and AUC (0.884) for predicting major amputation, followed by "
                "SINBAD (AUC: 0.812). Severe ischemia and deep tissue infection were the strongest predictors."
            ),
            "scraped_at": datetime.now().isoformat(),
        },
    ]

    def __init__(self, email: str = "soporte@piediabetico.lat"):
        self.email = email
        self.headers = {
            "User-Agent": f"PieDiabeticoLAT/2.0 (mailto:{self.email})",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.timeout = 15
        self.semana_pasada = (datetime.now() - timedelta(days=7)).strftime("%Y/%m/%d")

    # ─────────────────────────────────────────────────────────────
    # FUENTE 1: PUBMED
    # ─────────────────────────────────────────────────────────────

    def _buscar_pubmed(self, query: str, max_results: int) -> list:
        """Busca PMIDs en PubMed con una query MeSH."""
        params = {
            "db": "pubmed",
            "term": query + f" AND ({self.semana_pasada}[Date - Publication] : 3000[Date - Publication])",
            "retmode": "json",
            "retmax": max_results,
            "sort": "pub_date",
            "email": self.email,
        }
        try:
            r = requests.get(self.BASE_URL_SEARCH, params=params, headers=self.headers, timeout=self.timeout)
            r.raise_for_status()
            pmids = r.json().get("esearchresult", {}).get("idlist", [])
            logger.info(f"PubMed query → {len(pmids)} PMIDs encontrados")
            return pmids
        except Exception as e:
            logger.warning(f"Error buscando en PubMed: {e}")
            return []

    def _fetch_pubmed_details(self, pmids: list) -> list:
        """Descarga los detalles de una lista de PMIDs."""
        if not pmids:
            return []
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "email": self.email,
        }
        try:
            r = requests.get(self.BASE_URL_FETCH, params=params, headers=self.headers, timeout=self.timeout)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            articles = []
            for art in root.findall(".//PubmedArticle"):
                pmid_el    = art.find(".//PMID")
                title_el   = art.find(".//ArticleTitle")
                journal_el = art.find(".//Journal/Title")
                date_el    = art.find(".//JournalIssue/PubDate")

                pmid    = pmid_el.text if pmid_el is not None else "N/A"
                title   = "".join(title_el.itertext()).strip() if title_el is not None else "Sin título"
                journal = journal_el.text if journal_el is not None else "Desconocido"

                pub_date = "N/A"
                if date_el is not None:
                    year  = date_el.find("Year")
                    month = date_el.find("Month")
                    if year is not None:
                        pub_date = year.text + (f"-{month.text}" if month is not None else "")

                authors = []
                for author in art.findall(".//AuthorList/Author"):
                    ln = author.find("LastName")
                    fn = author.find("ForeName")
                    if ln is not None and fn is not None:
                        authors.append(f"{ln.text}, {fn.text}")
                author_str = "; ".join(authors[:3]) + (" y cols." if len(authors) > 3 else "")

                abstract_parts = []
                for ab in art.findall(".//Abstract/AbstractText"):
                    label = ab.attrib.get("Label")
                    text  = "".join(ab.itertext()).strip()
                    abstract_parts.append(f"**{label}:** {text}" if label else text)
                abstract = "\n\n".join(abstract_parts) or "Abstract no disponible."

                doi = "N/A"
                for el in art.findall(".//ArticleIdList/ArticleId"):
                    if el.attrib.get("IdType") == "doi":
                        doi = el.text
                        break

                articles.append({
                    "pmid": pmid,
                    "fuente": "PubMed",
                    "title": title,
                    "authors": author_str or "Autor institucional",
                    "journal": journal,
                    "pub_date": pub_date,
                    "doi": doi,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "abstract_raw": abstract,
                    "scraped_at": datetime.now().isoformat(),
                })
            logger.info(f"PubMed fetch → {len(articles)} artículos procesados")
            return articles
        except Exception as e:
            logger.warning(f"Error en fetch PubMed: {e}")
            return []

    def scrape_pubmed(self) -> list:
        """Ejecuta todas las queries de PubMed y consolida resultados."""
        todos_pmids = []
        for query, max_r in self.QUERIES_PUBMED:
            pmids = self._buscar_pubmed(query, max_r)
            todos_pmids.extend(pmids)

        # Deduplicar PMIDs
        todos_pmids = list(dict.fromkeys(todos_pmids))
        logger.info(f"PubMed total → {len(todos_pmids)} PMIDs únicos")

        if not todos_pmids:
            logger.warning("PubMed sin resultados esta semana → activando fallback")
            return self.MOCK_ARTICLES

        return self._fetch_pubmed_details(todos_pmids)

    # ─────────────────────────────────────────────────────────────
    # FUENTE 2: WEB SCRAPING GENÉRICO
    # ─────────────────────────────────────────────────────────────

    def _scrape_generic(self, fuente: dict) -> list:
        """
        Extrae títulos y links de una fuente web genérica.
        Busca etiquetas <article>, <h2>, <h3> con links.
        """
        try:
            r = requests.get(fuente["url"], headers=self.headers, timeout=self.timeout)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            items = []

            # Buscar artículos o titulares con link
            candidatos = (
                soup.find_all("article")[:5] or
                soup.find_all("h2")[:5] or
                soup.find_all("h3")[:5]
            )

            for el in candidatos:
                link = el.find("a")
                if not link:
                    continue
                titulo = link.get_text(strip=True)
                href   = link.get("href", "")
                if not titulo or len(titulo) < 20:
                    continue
                if not href.startswith("http"):
                    href = fuente["url"].rstrip("/") + "/" + href.lstrip("/")

                items.append({
                    "pmid": None,
                    "fuente": fuente["nombre"],
                    "title": titulo,
                    "authors": "Editorial",
                    "journal": fuente["nombre"],
                    "pub_date": datetime.now().strftime("%Y-%m"),
                    "doi": None,
                    "url": href,
                    "abstract_raw": f"Artículo publicado en {fuente['nombre']}. Ver el enlace para más detalles.",
                    "scraped_at": datetime.now().isoformat(),
                })

            logger.info(f"{fuente['nombre']} → {len(items)} artículos encontrados")
            return items

        except Exception as e:
            logger.warning(f"Error scrapeando {fuente['nombre']}: {e}")
            return []

    def scrape_fuentes_web(self) -> list:
        """Scrapea todas las fuentes web configuradas."""
        todos = []
        for fuente in self.FUENTES_WEB:
            items = self._scrape_generic(fuente)
            todos.extend(items)
        return todos

    # ─────────────────────────────────────────────────────────────
    # DEDUPLICACIÓN
    # ─────────────────────────────────────────────────────────────

    def _deduplicar(self, articles: list) -> list:
        """Elimina artículos duplicados por URL o PMID."""
        vistos = set()
        resultado = []
        for art in articles:
            clave = art.get("pmid") or art.get("url")
            if clave and clave not in vistos:
                vistos.add(clave)
                resultado.append(art)
        return resultado

    # ─────────────────────────────────────────────────────────────
    # PUNTO DE ENTRADA PRINCIPAL
    # ─────────────────────────────────────────────────────────────

    def execute_weekly_sync(
        self,
        output_path: str = "/workspace/scratch/raw_articles.json"
    ) -> bool:
        """
        Ejecuta la sincronización semanal completa:
        1. PubMed (4 queries MeSH)
        2. Fuentes web especializadas (5 fuentes)
        3. Deduplicación y guardado

        Retorna True si se guardaron artículos, False si falló.
        """
        logger.info("── Agente 1: Iniciando sincronización semanal ──")
        logger.info(f"   Período: desde {self.semana_pasada} hasta hoy")

        # PubMed
        articles_pubmed = self.scrape_pubmed()

        # Fuentes web
        articles_web = self.scrape_fuentes_web()

        # Consolidar y deduplicar
        todos = self._deduplicar(articles_pubmed + articles_web)
        logger.info(f"Total artículos únicos consolidados: {len(todos)}")

        if not todos:
            logger.error("Sin artículos para procesar esta semana.")
            return False

        # Guardar en disco
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(todos, f, indent=4, ensure_ascii=False)
            logger.info(f"✓ {len(todos)} artículos guardados en: {output_path}")
            return True
        except IOError as e:
            logger.error(f"Error al escribir {output_path}: {e}")
            return False

    # Mantener compatibilidad con versión anterior
    def search_guidelines(self, max_results=5) -> list:
        return self._buscar_pubmed(self.QUERIES_PUBMED[0][0], max_results)

    def fetch_details(self, pmids: list) -> list:
        if "MOCK_FALLBACK" in pmids:
            return self.MOCK_ARTICLES
        return self._fetch_pubmed_details(pmids)


if __name__ == "__main__":
    agent = PubMedScraperAgent()
    agent.execute_weekly_sync()
