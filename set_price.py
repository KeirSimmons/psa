import argparse
import json
import math

import numpy as np
import pandas as pd

from collection import Collection


class SetPrice:

    discount = 0.01 # Discount per additional card as %
    max_discount_stack = 10 # Max number of cards for discount to apply
    additional_discount = 0.00 # Additional % discount, applied after previous discounts
    rounding_unit = 100 # Round to the nearest _
    rounding_up = False

    def __init__(self, cert=None, certs=None, set=None, delete_set=None):
        self.cert = cert
        self.certs = certs
        self.set = set
        self.delete_set = delete_set if delete_set is not None else False
        self.to_update = {}

        self._validate_params()
        self._load_data()

        self._determine_action()

        self._update_prices()

    def _validate_params(self):
        all_params = [val for val in [self.cert, self.certs, self.set]]
        passed_params = sum([val is not None for val in all_params])
        if not passed_params:
            raise Exception("You must pass either 'cert', 'certs' or 'set'.")
        elif passed_params > 1:
            raise Exception("You can only pass one of 'cert', 'certs' or 'set'.")
        
        if self.certs is not None:
            # check no duplicates
            if len(set(self.certs)) != len(self.certs):
                raise Exception("Your set has repeated cards.")
            
            # check at least 2 cards
            if len(self.certs) < 2:
                raise Exception("A set must have at least two cards!")

        
    def _get_cards(self):
        self.collection = Collection()
        self.cards = None
        try:
            if self.cert is not None:
                self.cards = {self.cert: self.collection.get(self.cert)}
            elif self.certs is not None:
                self.cards = {cert: self.collection.get(cert) for cert in self.certs}
        except KeyError as e:
            raise Exception(f"One or more cert numbers were invalid, for example #{e}.")
        
        if self.cards is not None:
            for cert, card in self.cards.items():
                sale_data = card['selling']
                if sale_data['sold'] is not None:
                    raise Exception(f"Card #{cert} has already been sold.")
                elif "price" not in sale_data or sale_data['price'] == 0:
                    raise Exception(f"You have not yet set a price for card #{cert}.")

    def _load_data(self):
        with open("./set_prices.json", "r") as fh:
            self.data = json.loads(fh.read())

    def _determine_action(self):
        # Find all sets that cert is a part of
        if self.cert is not None:
            self._get_cards()
            self._single_cert_flow()
        elif self.certs is not None:
            self._get_cards()
            self._make_set_flow()
        elif self.set is not None:
            self._set_flow()

    def _single_cert_flow(self):
        sets = self._find_sets_by_cert(self.cert)
        print(f"Card #{self.cert} is a member of {len(sets)} sets:")
        print(sets)

    def _make_set_flow(self):
        set_id = self._get_set_from_certs(self.certs) # if the set already exists this will be set
        if set_id is not None:
            raise Exception(f"This set already exists (#{set_id})")
        price = self._calculate_set_price(self.certs)
        no_of_cards = len(self.certs)
        discount = price['original'] - price['discounted']
        discount_pct = 100 - (price['discounted'] / price['original'] * 100)
        print(f"This set with {no_of_cards} cards will be priced at {price['discounted']} JPY, a {discount} JPY discount ({discount_pct:.02f}% off) from the original price of {price['original']} JPY.")

        if input("Do you want to log this set? [Y/n] ") == "Y":
            certs = self.certs
            set_id = self._get_next_autoincrement_id()
            self.data['next_autoincrement_id'] = str(int(set_id) + 1)
            self.data['sets'][set_id] = {
                "certs": certs,
                "price": price['discounted']
            }

            for cert in certs:
                if cert in self.data['certs']:
                    self.data['certs'][cert].append(set_id)
                else:
                    self.data['certs'][cert] = [set_id]

            self._save_data()

    def _calculate_set_price(self, certs):
        prices = []

        for cert in certs:
            card = self.collection.get(cert)
            prices.append(card['selling']['price'])
        
        base_discount = 1.00 - SetPrice.discount
        max_stack = SetPrice.max_discount_stack
        # apply discount per additional card in set
        discount = np.power(base_discount, min(max_stack, len(prices) - 1))

        # Apply additional discount
        discount *= (1.00 - SetPrice.additional_discount)
        
        original_price = sum(prices)
        discounted_price = original_price * discount

        rounding_unit = SetPrice.rounding_unit
        if rounding_unit  > 0:
            round_fn = math.ceil if SetPrice.rounding_up else math.floor
            discounted_price = round_fn(discounted_price / rounding_unit) * rounding_unit

        if discounted_price < 0:
            raise Exception(f"Discounted price is negative.")

        return {"original": original_price, "discounted": discounted_price}
    
    def _get_set_from_certs(self, certs):
        initial_cert = certs[0]
        cert_set = set(certs)
        if initial_cert in self.data['certs']:
            for set_id in self.data['certs'][initial_cert]:
                set_to_check = set(self.data['sets'][set_id]['certs'])
                if set_to_check == cert_set:
                    return set_id
        return None


    def _set_flow(self):
            id = self.set
            print(f"Information for the set #{id}.")
            print(self._get_set_from_id(id, recalculate=False))
            
            if self.delete_set:
                if input("Are you sure you want to delete this set? [Y/n] ") == "Y":

                    # Remove set from all affected certs
                    affected_certs = self.data['sets'][id]['certs']
                    for cert in affected_certs:
                        if cert in self.data['certs']:
                            set_data = set(self.data['certs'][cert])
                            if id in set_data:
                                set_data.remove(id)
                            if len(set_data):
                                self.data['certs'][cert] = list(set_data)
                            else:
                                del self.data['certs'][cert]

                    # Now remove from set
                    del self.data['sets'][id]
                    self._save_data()
                else:
                    print("Set was not deleted.")

    def _save_data(self):
        with open("./set_prices.json", "w") as fh:
            fh.write(json.dumps(self.data, indent=4))
        print("Data was overwritten.")
            
    
    def _get_next_autoincrement_id(self):
        id = self.data['next_autoincrement_id']
        if id in self.data['sets']:
            raise Exception("Next autoincrement ID is already in use.")
        return str(id)
    
    def _find_sets_by_cert(self, cert):
        if cert not in self.data['certs']:
            raise Exception(f"Card #{cert} is not currently being sold in any sets.")        
        data = self._get_sets_from_ids(self.data['certs'][cert])
        return data
    
    def _get_set_from_id(self, id, recalculate=True):
        return self._get_sets_from_ids([id], recalculate=recalculate)
    
    def _get_sets_from_ids(self, ids, recalculate=True):

        data = []
        for id in ids:
            if id not in self.data['sets']:
                raise Exception(f"Set #{id} does not exist.")

            set_data = self.data['sets'][id]

            if recalculate:
                new_price = self._calculate_set_price(set_data['certs'])['discounted']
                if new_price != set_data['price']:
                    self.to_update[id] = new_price
                set_data = [id, set_data['price'], new_price, set_data['certs']]
                cols = ["Set #", "Current Price [JPY]", "Updated Price [JPY]", "Cards"]
            else:
                set_data = [id, set_data['price'], set_data['certs']]
                cols = ["Set #", "Price [JPY]", "Cards"]


            data.append(set_data)

        data = pd.DataFrame(np.asarray(data), columns=cols)

        return data
    
    def _update_prices(self):
        if len(self.to_update) and input("Would you like to update the sets to their new prices? [Y/n] "):
            for id, new_price in self.to_update.items():
                self.data['sets'][id]['price'] = new_price
            self._save_data()
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert", default=None, help="A single cert when you want to find all current set details")
    parser.add_argument("--certs", default=None, nargs='+', help="List of certs for which you want to create a set on")
    parser.add_argument("--set", default=None, help="The ID of a set you want more information on")
    parser.add_argument("--delete_set", default=None, action="store_true", help="If passed, the set will be deleted (works with --set only).")
    args = parser.parse_args()

    SetPrice(cert=args.cert, certs=args.certs, set=args.set, delete_set=args.delete_set)