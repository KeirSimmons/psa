import copy
import json
from collections import abc, defaultdict

from dex import Dex
from sets import Sets


def merge_dictionaries(base, update):
    """Performs a deep, nested dictionary update.

    Modified from: https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth

    Args:
        base (dict): The base/default dictionary
        update (dict): The dictionary which has the overriding values

    Returns:
        dict: The updated dictionary
    """
    base = copy.deepcopy(base)
    for key, val in update.items():
        if isinstance(val, abc.Mapping):
            base[key] = merge_dictionaries(base.get(key, {}), val)
        else:
            base[key] = val
    return base


class Collection:
    def __init__(self):
        self.dex = Dex()
        self._load_default()
        self._load_collection()
        self._apply_defaults()
        self.validate()

    def _load_collection(self):
        with open("./collection.json", "r") as fh:
            self._data = json.loads(fh.read())
        self._flatten_data()
        self._organise()

    def _load_default(self):
        with open("./default.json", "r") as fh:
            self.default = json.loads(fh.read())

    def _apply_defaults(self):
        for cert, card in self.data.items():
            self.data[cert] = merge_dictionaries(self.default, card)

    def validate(self):
        for psa, card in self.data.items():
            self._validate_card(psa, card)
        return True

    def _validate_card(self, psa, card):
        valid_keys = set(self.default.keys()).union({"year"})
        supplied_keys = card.keys()

        additional_keys = supplied_keys - valid_keys
        if additional_keys:
            raise Exception(
                f"Card {psa} has at least one invalid entry ({additional_keys})"
            )

        required_keys = {"grade"}
        unsupplied_required_keys = required_keys - supplied_keys
        if unsupplied_required_keys:
            raise Exception(
                f"Card {psa} did not supply required entries ({unsupplied_required_keys})"
            )

        if (
            ("set" in card)
            and (card["set"] is not None)
            and (card["set"] not in Sets.__members__)
        ):
            # Set was provided but doesn't exist
            raise Exception(f"Card {psa} does not have a valid set ({card['set']})")

    def _flatten_data(self):
        all = {}
        for year, collection in copy.deepcopy(self._data).items():
            existing_certs = set(all.keys())
            incoming_certs = set(collection.keys())
            overlapping_certs = existing_certs.intersection(incoming_certs)
            if overlapping_certs:
                # Some keys already existed:
                raise Exception(f"Keys {overlapping_certs} appeared more than once.")
            for cert, card in collection.items():
                # collection[cert] = merge_dictionaries(self.default, card)
                collection[cert]["year"] = year
            all.update(collection)
        self.data = all
        return all

    @staticmethod
    def get_attr(card, attr):
        if attr in card:
            return str(card[attr])
        else:
            return "NONE"

    def _organise(self):

        hash = defaultdict(lambda: defaultdict(list))
        for year, collection in self._data.items():
            for cert, card in collection.items():
                card_hash = f"{year}-{Collection.get_attr(card, 'language')}"
                if "pkmn" in card:
                    card_hash += f"-{card['pkmn']}"
                elif "energy" in card:
                    card_hash += "-energy"
                elif "trainer" in card:
                    card_hash += "-trainer"

                base_hash = card_hash

                # L1 equivalence if year & language & dex number are the same
                hash[card_hash]["l1"].append(cert)

                # L2 equivalence if L1 & set are the same
                card_hash += f"-{Collection.get_attr(card, 'set')}"
                hash[base_hash]["l2"].append(cert)

                # L3 equivalence if L2 & card details are the same
                details = [
                    "1st",
                    "base_no_rarity",
                    "shadowless",
                    "shining",
                    "FA",
                    "EX",
                    "M",
                    "LV.X",
                    "LEGEND",
                    "BREAK",
                    "bandai",
                    "topsun_nonumber",
                    "promo",
                ]
                for detail in details:
                    card_hash += f"-{Collection.get_attr(card, detail)}"
                hash[base_hash]["l3"].append(cert)

                # L4 equivalence if L3 & sign existence are the same
                does_sign_exist = str("sign" in card)
                card_hash += f"-{does_sign_exist}"
                hash[base_hash]["l4"].append(cert)

                # L5 equivalence if L4 & notes are the same
                card_hash += f"-{Collection.get_attr(card, 'notes')}"
                hash[base_hash]["l5"].append(cert)

                # L6 equivalence if L5 & grade/sign grade are equivalent
                card_hash += f"-{Collection.get_attr(card, 'grade')}"
                card_hash += f"-{Collection.get_attr(card, 'sign')}"
                hash[base_hash]["l6"].append(cert)

        for base_hash, levels in hash.items():
            base_cards = levels["l6"]
            base_cards = {cert: 1 / 6 for cert in base_cards}
            for cert in levels["l1"]:
                for level in ["l5", "l4", "l3", "l2", "l1"]:
                    if cert in levels[level]:
                        base_cards[cert] += 1 / 6
            hash[base_hash]["prob"] = base_cards

        self.hash = hash
        return self.hash

    def find_dupes(self, cert):
        cert = str(cert)
        matches = []
        for base_hash, levels in self.hash.items():
            results = levels["prob"]
            if cert in results.keys():
                matches.append(
                    {
                        "base_hash": base_hash,
                        "match_prob": results[cert],
                        "certs": self.hash[base_hash]["l1"],
                    }
                )

        return [
            match
            for match in sorted(
                matches, reverse=True, key=lambda matches: matches["match_prob"]
            )
        ]

    def find_same_attr(self, cert, attr):
        cert = str(cert)
        attr_val = Collection.get_attr(self.data[cert], attr)
        matches = []
        for _cert, card in self.data.items():
            _attr_val = Collection.get_attr(card, attr)
            if attr_val == _attr_val:
                matches.append(_cert)

        if attr == "pkmn":
            attr_val = self.dex.find_from_dex(int(attr_val))["name"]["english"].upper()

        return matches, attr_val

    def find_same_bg_pkmn(self, cert):
        cert = str(cert)
        pkmn = Collection.get_attr(self.data[cert], "pkmn")

        matches = []
        for _cert, card in self.data.items():
            bg_pkmn = card["contains_pkmn"]
            if pkmn in bg_pkmn:
                matches.append(_cert)

        return matches

    def find_most_dupes(self):
        matches = {}
        for cert in self.data.keys():
            dupes = self.find_dupes(cert)
            no_of_dupes = sum([len(x["certs"]) for x in dupes])
            matches[cert] = no_of_dupes
        return next(
            iter(
                {
                    k: v
                    for k, v in sorted(
                        matches.items(), key=lambda x: x[1], reverse=True
                    )
                }.items()
            )
        )

    def get(self, cert, replace=False):
        card = self.data[cert]
        if replace:
            card["pkmn_name"] = self.dex.find_from_dex(int(card["pkmn"]))["name"][
                "english"
            ].upper()
            card["contains_pkmn_names"] = [
                self.dex.find_from_dex(int(_pkmn))["name"]["english"].upper()
                for _pkmn in card["contains_pkmn"]
            ]
        return card

    def update(self, cert, updated_card):
        year = updated_card["year"]
        updated_card["year"] = None
        updated_card = {k: v for k, v in updated_card.items() if v is not None}
        self._data[year][cert] = updated_card
        with open("./collection.json", "w") as fh:
            fh.write(json.dumps(self._data, indent=4))


if __name__ == "__main__":
    collection = Collection()
    print(collection.find_dupes(27574940))
    print(collection.find_same_attr(27574940, "pkmn"))
    print(collection.find_same_attr(27574940, "set"))

    cert, count = collection.find_most_dupes()
    card = collection.get(cert)
    print(f"Most dupes ({count}):")
    print(card)
