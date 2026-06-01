"""FinanceBrainDomain — proof that F49 generalizes beyond TJ.

Mirrors the structural contract of jw_brain.schema.NodeTypeSpec /
EdgeTypeSpec without importing from jw_brain (so the plugin stays
decoupled — exactly the goal of F41).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NodeSpec:
    name: str
    canonical_id_pattern: str
    properties: dict = field(default_factory=dict)
    wiki_page_template: str = ""
    obsidian_subdir: str = ""
    confidence_threshold: float = 0.5


@dataclass(frozen=True)
class EdgeSpec:
    name: str
    sources: tuple = ()
    targets: tuple = ()
    directional: bool = True
    confidence_threshold: float = 0.5
    sensitive: bool = False


class FinanceBrainDomain:
    name = "finance"

    nodes = [
        NodeSpec(
            "Transaction",
            "tx:{date}:{amount}:{hash}",
            {"date": str, "amount": float, "currency": str},
            wiki_page_template="transaction.md",
            obsidian_subdir="transactions/",
        ),
        NodeSpec(
            "Vendor",
            "vendor:{slug}",
            {"slug": str, "name": str},
            wiki_page_template="vendor.md",
            obsidian_subdir="vendors/",
        ),
        NodeSpec(
            "Category",
            "cat:{slug}",
            {"slug": str, "label": str},
            wiki_page_template="category.md",
            obsidian_subdir="categories/",
        ),
        NodeSpec(
            "TaxYear",
            "tax:{year}",
            {"year": int},
            wiki_page_template="tax_year.md",
            obsidian_subdir="fiscal-events/",
        ),
    ]
    edges = [
        EdgeSpec("PAID_TO", sources=("Transaction",), targets=("Vendor",)),
        EdgeSpec("CATEGORIZED_AS", sources=("Transaction",), targets=("Category",)),
        EdgeSpec("AFFECTS_TAX", sources=("Transaction",), targets=("TaxYear",)),
    ]
