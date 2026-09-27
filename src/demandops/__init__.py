"""DemandOps — Quick-Commerce Demand & Inventory Decision Platform.

Package layout (layers are added incrementally as milestones complete):
- ingestion / validation  (Layer 1)
- SQL analytics           (Layer 2, queries live in /sql)
- forecasting             (Layer 3)
- stockout risk           (Layer 4)
- recommendations         (Layer 5)
- what-if simulation      (Layer 6)
- API                     (Layer 7)
- dashboard               (Layer 8)
"""

__version__ = "0.1.0"
