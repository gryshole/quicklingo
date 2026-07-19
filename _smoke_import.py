import importlib, pkgutil, traceback, quicklingo
fails = []
for m in pkgutil.walk_packages(quicklingo.__path__, "quicklingo."):
    if m.ispkg:
        continue
    try:
        importlib.import_module(m.name)
    except Exception as e:
        fails.append((m.name, repr(e)))
if fails:
    for name, err in fails:
        print("FAIL", name, err)
else:
    print("ALL IMPORTS OK")
