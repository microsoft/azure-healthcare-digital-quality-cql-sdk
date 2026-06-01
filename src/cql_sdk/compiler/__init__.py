"""Compiler / planning layer.

This layer bridges ELM nodes to executable runtime behavior. In the initial
scaffold the runtime interprets ELM directly; the planner is kept as a
seam so a future version can pre-bake expression trees into compiled
callables without changing the public API.
"""
