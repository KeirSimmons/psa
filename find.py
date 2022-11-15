import argparse

from collection import Collection


def find(cert):
    collection = Collection()
    print(f"Details for card of cert {cert}:")
    print(collection.get(cert, replace=True))

    print("\nPossible equivalent cards:")
    print(collection.find_dupes(cert))

    same, pkmn = collection.find_same_attr(27574940, "pkmn")
    print(f"\nCards with the same Pokemon ({pkmn}):")
    print(same)

    same = collection.find_same_bg_pkmn(27574940)
    print(f"\nCards with the same Pokemon in the background ({pkmn}):")
    print(same)

    same, _set = collection.find_same_attr(27574940, "set")
    print(f"\nCards in the same set ({_set}):")
    print(same)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cert")
    args = parser.parse_args()
    find(args.cert)
