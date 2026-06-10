"""Job-searcher agent: provider-agnostic job search.

``provider`` defines the :class:`JobProvider` interface and the normalized
:class:`JobPosting`; concrete backends (e.g. :class:`adzuna.AdzunaProvider`)
implement it.
"""
