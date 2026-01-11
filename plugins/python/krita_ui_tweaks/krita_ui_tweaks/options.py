# SPDX-License-Identifier: CC0-1.0

import os
import json
import typing


C = dict[str, dict[str, str | bool]]

_global_config: C | None = None

_FORCED_TOGGLES: dict[str, bool] = {
    "split_panes": True,
    "toolbar_icons": True,
    "shared_tool": True,
}


def defaultConfig() -> C:
    config: C = {
        "translated": {
            "Consolidate All": "Consolidate All",
            "Close": "Close",
            "Close All": "Close All",
            "Close Others": "Close Others",
            "Close Split Pane": "Close Split Pane",
            "Reset Sizes": "Reset Sizes",
            "New Document": "New Document",
            "Open Document": "Open Document",
            "Goto next tab": "Goto next tab",
            "Goto previous tab": "Goto previous tab",
        },
        "toggle": {
            "split_panes": True,
            "toolbar_icons": True,
            "shared_tool": True,
        },
    }
    return config


def getOpt(*args: str):
    if len(args) == 2 and args[0] == "toggle":
        forced = _FORCED_TOGGLES.get(args[1])
        if forced is not None:
            return forced

    global _global_config
    if _global_config is None:
        _global_config = readConfig()
    val = _global_config
    numArgs = len(args)
    for i, a in enumerate(args):
        val = typing.cast(dict[str, str | bool], val).get(a, None)
        if not isinstance(val, dict) and i < numArgs - 1:
            val = None
            break
    return val


def readConfig():
    config = None
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config.json"
    )
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    defaults = defaultConfig()

    if isinstance(config, dict):
        config = typing.cast(C, config)
        for section in ("translated", "toggle"):
            if not isinstance(config.get(section, None), dict):
                config[section] = defaults[section]
            else:
                for _, (k, v) in enumerate(defaults[section].items()):
                    s = config[section]
                    if s.get(k, None) is None:
                        s[k] = v
        return config
    else:
        return defaults


def writeConfig(config: C):
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config.json"
    )
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass
