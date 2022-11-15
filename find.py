import argparse

from collection import Collection


def find(cert, price):
    collection = Collection()

    print(f"Details for card of cert {cert}:")
    data = collection.get(cert, replace=True)
    print(data)

    if price:
        print(f"To be sold at {data['selling']['price']} JPY")
    else:

        print("\nPossible equivalent cards:")
        print(collection.find_dupes(cert))

        same, pkmn = collection.find_same_attr(cert, "pkmn")
        print(f"\nCards with the same Pokemon ({pkmn}):")
        print(same)

        same = collection.find_same_bg_pkmn(cert)
        print(f"\nCards with the same Pokemon in the background ({pkmn}):")
        print(same)

        same, _set = collection.find_same_attr(cert, "set")
        print(f"\nCards in the same set ({_set}):")
        print(same)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cert")
    parser.add_argument("--price", default=False, action="store_true")
    args = parser.parse_args()
    find(args.cert, args.price)
