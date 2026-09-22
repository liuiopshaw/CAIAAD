"""Tools package.

Only the AD-domain runtime tools remain here:

- ``pubchem_tool`` / ``materials_project_tool`` / ``drugbank_tool`` /
  ``nanolit_search_tool`` — material & small-molecule discovery and lookup
- ``chembl_tool`` / ``uniprot_tool`` / ``opentargets_tool`` — verification of
  SMILES, UniProt accessions, and target-disease associations

All CrewAI tool wrappers and the original water-treatment / material-design
tools (PNEC, MolPort, ECOSAR, enzyme classifier, structure validators, ...)
were removed. Scripts import the submodules directly, e.g.::

    from src.tools.chembl_tool import molecule_by_smiles

This ``__init__`` intentionally imports nothing so that ``import src.tools``
never pulls in third-party dependencies or dead code.
"""
