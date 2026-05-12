import ragas
import pkgutil

def find_submodules(package):
    for loader, modname, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        if 'simple' in modname or 'evolution' in modname or 'synthesizer' in modname:
            print(f"Found: {modname}")

if __name__ == "__main__":
    find_submodules(ragas)
