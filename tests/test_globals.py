"""
Regression tests for the IOC_BUILD_NAME vs IOC_NAME distinction.

A legacy-built RTEMS IOC has two genuinely different names:
  * the build folder basename (IOC_ORIGINAL_LOCATION.name), which the source
    .boot binary is named after, e.g. 'bl-va-ioc-01' -> 'BL-VA-IOC-01.boot'
  * the deployment/instance name (IOC_NAME), used for the TFTP/NFS/boot paths,
    e.g. 'bl19i-va-ioc-01'

Deriving IOC_NAME from the build folder produced the wrong TFTP boot path
(/iocs/bl-va-ioc-01/rtems.ioc.bin). These tests pin the two names apart.
"""

import os

from rtems_proxy.globals import GLOBALS, reload_globals


def test_build_name_and_ioc_name_differ(monkeypatch):
    monkeypatch.setenv(
        "IOC_ORIGINAL_LOCATION", "/dls_sw/work/R7.0.7/ioc/BL/bl-va-ioc-01"
    )
    monkeypatch.setenv("IOC_NAME", "bl19i-va-ioc-01")
    reload_globals()
    try:
        # IOC_BUILD_NAME is the build folder basename (the source boot image is
        # now the generic 'ioc.boot', so the name is no longer derived from this)
        assert GLOBALS.IOC_BUILD_NAME == "bl-va-ioc-01"

        # deployment name drives the TFTP boot path and must not equal the build
        # folder name for this legacy IOC
        assert GLOBALS.IOC_NAME == "bl19i-va-ioc-01"
        assert GLOBALS.IOC_BUILD_NAME != GLOBALS.IOC_NAME
        assert "bl19i-va-ioc-01" in GLOBALS.RTEMS_EPICS_BINARY
    finally:
        # restore GLOBALS to the ambient environment for other tests
        for key in ("IOC_ORIGINAL_LOCATION", "IOC_NAME"):
            os.environ.pop(key, None)
        reload_globals()
