---
html_theme.sidebar_secondary.remove: true
---

```{include} ../README.md
:end-before: <!-- README only content
```

:::{important}
These docs assume a Diamond Light Source environment throughout: `/dls_sw` for
the Generic IOC build trees and support module templates, the module system for
`ec` and `uv`, podman on managed workstations, and the Argus cluster for
deployment. Commands are written to be run as-is at DLS rather than qualified
for a general audience. For the facility-neutral epics-containers documentation
see <https://epics-containers.github.io/>, and for wider DLS practice see the
[DLS developer guide](https://dev-guide.diamond.ac.uk/epics-containers/).
:::


How the documentation is structured
-----------------------------------

Documentation is split into [four categories](https://diataxis.fr), also accessible from links in the top bar.

<!-- https://sphinx-design.readthedocs.io/en/latest/grids.html -->

::::{grid} 2
:gutter: 4

:::{grid-item-card} {material-regular}`directions_walk;2em`
```{toctree}
:maxdepth: 2
tutorials
```
+++
Tutorials for installation and typical usage. New users start here.
:::

:::{grid-item-card} {material-regular}`directions;2em`
```{toctree}
:maxdepth: 2
how-to
```
+++
Practical step-by-step guides for the more experienced user.
:::

:::{grid-item-card} {material-regular}`info;2em`
```{toctree}
:maxdepth: 2
explanations
```
+++
Explanations of how it works and why it works that way.
:::

:::{grid-item-card} {material-regular}`menu_book;2em`
```{toctree}
:maxdepth: 2
reference
```
+++
Technical reference material including APIs and release notes.
:::

::::
