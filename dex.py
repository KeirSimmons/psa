import argparse
import json


class Dex:
    def __init__(self):
        with open("./pkmn.json", "r") as fh:
            dex = json.loads(fh.read())

        self._dex = dex
        self.dex = dict()

        for dex_num, data in enumerate(dex):
            self.dex[data["name"]["english"].upper()] = data

    def find(self, pkmn):
        pkmn = pkmn.upper()
        return pkmn, self.dex[pkmn]["id"]

    def find_from_dex(self, dex):
        for card in self._dex:
            if card["id"] == dex:
                return card


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pkmn")
    args = parser.parse_args()
    print(Dex().find(args.pkmn))
