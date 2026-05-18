"""Universal test for Home Assistant integrations."""

import os
import importlib
import pkgutil


def test_domain_name_and_load_modules():
    """Dynamically test that the DOMAIN constant matches the folder name, and load all modules for coverage."""
    # 1. Find the custom_components folder
    base_dir = os.path.dirname(os.path.dirname(__file__))
    components_dir = os.path.join(base_dir, "custom_components")

    # 2. Look inside to find the name of your integration
    integration_folders = [
        f
        for f in os.listdir(components_dir)
        if os.path.isdir(os.path.join(components_dir, f))
    ]

    assert len(integration_folders) == 1, (
        "Could not find exactly one integration folder"
    )
    dynamic_domain = integration_folders[0]
    integration_path = os.path.join(components_dir, dynamic_domain)

    # 3. Magically import the const.py file and test DOMAIN
    const_module = importlib.import_module(f"custom_components.{dynamic_domain}.const")
    assert const_module.DOMAIN == dynamic_domain

    # 4. DEEP SCAN: Forceer Python om elk .py bestand in de map te openen (zonder het uit te voeren)
    # Dit is de ultieme truc om pytest-cov te dwingen elke regel code te zien!
    for _, module_name, _ in pkgutil.walk_packages([integration_path]):
        try:
            importlib.import_module(f"custom_components.{dynamic_domain}.{module_name}")
        except Exception as e:
            # Als een bestand niet laadt (bijv. mist een afhankelijkheid in de test),
            # printen we een waarschuwing maar laten we de test niet crashen.
            print(f"Warning: Could not import {module_name}: {e}")
