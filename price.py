import argparse
import json
import math
from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd

from collection import Collection
from dex import Dex
from stats import Stats


class CardNoSalesDataException(Exception):
    pass


class Price:
    def __init__(self, cert, recalculate, copy_cert):
        self.cert = cert
        self.recalculate = recalculate
        self.copy_cert = copy_cert
        self.collection = Collection()
        self.dex = Dex()
        self.stats = Stats()

    def _set_card(self, cert):
        self.cert = cert
        self.card = self.collection.get(cert)

    def _card_title(self, cert):
        try:
            pkmn = self.dex.find_from_dex(self.card["pkmn"])["name"]["english"]
        except TypeError:
            pkmn = "(unknwn card)"
        grade = self.card["grade"]
        print(f"Adjusting the price for card #{cert} (PSA {grade} {pkmn})")

    def act(self):

        if self.recalculate:
            # We either recalculate all or just for a single cert
            if self.cert is not None:
                self._recalculate_cert(self.cert)
            else:
                self._recalculate_all_certs()

        else:
            # Cert is now required
            if self.cert is None:
                raise Exception("Cert must be passed.")
            self._set_card(self.cert)
            self._card_title(self.cert)

            if self.copy_cert is not None:
                self._set_from_other_cert(self.copy_sert)
            else:
                self._set_from_sales_data()

    def _recalculate_cert(self, cert):
        self._set_card(cert)

        if self.card["sales_data"]["avg_price"] == 0:
            raise CardNoSalesDataException(
                f"Card #{cert} doesn't have any sales data so cannot have its price recalculated."
            )

        self._set_from_other_cert(cert)

    def _recalculate_all_certs(self):
        for cert, _ in self.collection.get_next_card():
            try:
                self._recalculate_cert(cert)
            except CardNoSalesDataException:
                continue

    def _set_from_other_cert(self, copy_cert):
        other_card = self.collection.get(copy_cert)
        sales_data = other_card["sales_data"]["medium"]

        pricing_data = []
        for website in sales_data.keys():
            for status in sales_data[website].keys():
                sales = sales_data[website][status]
                for sale in sales:
                    grade = sale["grade"]
                    price = sale["price"]
                    scale_factor, weight = self._get_scale_factor(
                        website, status, grade
                    )
                    pricing_data.append((price, scale_factor, weight, grade))

        self.pricing_data = pricing_data
        self.prices_dict = {"medium": sales_data}

        self._calculate()
        self._save()

    def _get_min_selling_price(self, ebay=False, mercari=False):
        assert ((not ebay) or (not mercari) and (mercari or ebay)), "You must set either ebay or mercari to True"
        medium = "ebay" if ebay else mercari
        try:
            sales_data = self.card["sales_data"]["medium"][medium]["selling"]
            min_price = min([card['price'] for card in sales_data])
            return min_price
        except KeyError:
            return None
        except ValueError:
            return None


    def _set_from_sales_data(self):
        price = self.card["selling"]["price"]

        # Get individual selling data
        ebay_min = self._get_min_selling_price(ebay=True)
        mercari_min = self._get_min_selling_price(mercari=True)
        if ebay_min is not None:
            print(f"Cheapest eBay price: {ebay_min} JPY")
        else:
            print("No selling data for eBay")
        if mercari_min is not None:
            print(f"Cheapest Mercari price: {mercari_min} JPY")
        else:
            print("No selling data for Mercari")

        if price > 0:
            # price has been set before
            print(f"The price has already been set at {price} JPY.")
            overwrite = (
                input(
                    "Are you sure you want to overwrite the price? [Y/n]\n > "
                ).lower()
                == "y"
            )

            if not overwrite:
                raise Exception("Ending.")

        self._collect_prices()
        self._save()

    def _collect_prices(self):

        prices = []
        weights = []
        pricing_data = []
        prices_dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        continuing = True
        for website in ["ebay", "mercari"]:
            if not continuing:
                break
            for status in ["selling", "sold"]:
                if not continuing:
                    break
                print(f"\nYou are now inspecting items on {website} ({status})")
                while True:
                    data = input(
                        "Input the price and grade with a comma separating. '10000,5' for example.\n[Enter 'c' to skip, 'e' to finish, 'q' to quit].\n > "
                    )
                    if data == "c":
                        print("Skipping.")
                        break
                    elif data == "e":
                        continuing = False
                        break
                    elif data == "q":
                        raise Exception("Quit.")
                    try:
                        price, grade = [int(x) for x in data.split(",")]
                    except ValueError as e:
                        print(e)
                        continue
                    if not (1 <= grade <= 10):
                        print("Grade must be between [1, 10]")
                        continue
                    elif price <= 0:
                        print("Price must be greater than 0")
                        continue

                    scale_factor, weight = self._get_scale_factor(
                        website, status, grade
                    )
                    adjusted_price = int(price * scale_factor)
                    prices.append(adjusted_price)
                    weights.append(weight)
                    pricing_data.append((price, scale_factor, weight, grade))
                    prices_dict["medium"][website][status].append(
                        {
                            "price": price,
                            "grade": grade,
                        }
                    )

                    print(
                        f"-> Logging a PSA {grade} at {price} JPY. Adjusted to {adjusted_price} (SF: {scale_factor:.02f})."
                    )

        if not prices:
            raise Exception("No prices were added.")

        self.pricing_data = pricing_data
        self.prices_dict = prices_dict
        self._calculate()

    def _calculate(self):
        pricing_data = self.pricing_data
        original_price = np.asarray([x[0] for x in pricing_data])
        original_scale = np.asarray([x[1] for x in pricing_data])
        grades = np.asarray([x[3] for x in pricing_data])
        scaled_prices = original_price * original_scale

        avg_scaled_price = np.mean(scaled_prices)
        std_scaled_price = np.std(scaled_prices)

        # Weights we apply for distance from mean
        if std_scaled_price < 1e-5:
            std_weights = np.ones((len(scaled_prices),))
        else:
            std_weights = 1 / np.clip(
                abs((scaled_prices - avg_scaled_price) / std_scaled_price),
                1,
                1000,
            )

        # Weights provided by source
        original_weights = np.asarray([x[2] for x in pricing_data])

        # Final weights
        weights_to_use = std_weights * original_weights

        # Weighted average
        scaled_avg_price = int(
            sum(scaled_prices * weights_to_use) / sum(weights_to_use)
        )

        previous_price = self.card["selling"]["price"]
        if abs(scaled_avg_price - previous_price) <= 1e-5:
            self.price_changed = False
            return None
        else:
            self.price_changed = True

        as_jpy = lambda vals: [f"{int(val)} JPY" for val in vals]
        as_flt = lambda vals: [f"{val:.02f}" for val in vals]
        as_int = lambda vals: [int(val) for val in vals]

        df_data = np.asarray(
            [
                as_int(grades),
                as_jpy(original_price),
                as_flt(original_scale),
                as_jpy(scaled_prices),
                as_flt(original_weights),
                as_flt(std_weights),
                as_flt(weights_to_use),
            ]
        ).T

        df = (
            pd.DataFrame(
                df_data,
                columns=[
                    "Grade",
                    "Orig. Price",
                    "Orig. Scale",
                    "Scaled Price",
                    "Orig. Weights",
                    "STD Weights",
                    "Final weights",
                ],
            )
            .astype({"Grade": int})
            .sort_values(by=["Grade"])
        )

        self._card_title(self.cert)

        print("Sales data:\n")

        print(df)
        price_without_weighting = int(sum(scaled_prices) / len(scaled_prices))
        price_without_std_weighting = int(
            sum(scaled_prices * original_weights) / sum(original_weights)
        )
        print(f"\nPrice without any weighting: {price_without_weighting} JPY")
        print(f"Price without std weighting: {price_without_std_weighting} JPY")
        print(f"Price with all weighting: {scaled_avg_price} JPY (chosen)")
        if previous_price > 0:
            print(f"Original price was {previous_price} JPY.")

        self.avg_price = scaled_avg_price
        self.sales_data = self.prices_dict

    def _get_scale_factor(self, website, status, grade):
        multipliers = {"base": 1.1, "grade": 0.7, "pseudo_10": 11, "signed": 10}

        weightings = {
            "same_grade": 1.2,
            "ebay_selling": 1,
            "ebay_sold": 1.2,
            "mercari_selling": 1.25,
            "mercari_sold": 1.5,
        }

        website_status = f"{website}_{status}"
        weighting = weightings[website_status]
        multiplier = multipliers["base"]

        card_grade = self.card["grade"]
        card_sign = self.card["sign"]

        if card_grade == grade:
            weighting *= weightings["same_grade"]

        if card_sign:
            multiplier *= multipliers["signed"]

        if card_grade == 10:
            card_grade = multipliers["pseudo_10"]
        if grade == 10:
            grade = multipliers["pseudo_10"]

        multiplier *= math.pow(multipliers["grade"], grade - card_grade)

        return multiplier, weighting

    def _save(self):

        if not self.price_changed:
            print(f"Card #{self.cert}'s price did not change.")
            return None

        okay = input(
            f"\n\nWe have calculated a price of {self.avg_price} JPY - is this okay to set?\n[Y/n] ('q' to quit and save nothing)\n > "
        ).lower()
        if okay == "q":
            raise Exception("Ending, no sales data was saved.")
        self.card["sales_data"] = json.loads(json.dumps(self.sales_data))
        self.card["sales_data"]["avg_price"] = self.avg_price
        self.card["sales_data"]["last_updated"] = date.today().strftime("%Y-%m-%d")
        if okay == "y":
            print(f"Updating selling price.")
            self.card["selling"]["price"] = self.avg_price
        self.collection.update(self.cert, self.card)
        print(f"Card successfully updated (#{self.cert}).")

        self._calculate_stats()

    def _calculate_stats(self):
        print("\nCalculating stats...")
        self.stats.calculate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert", default=None)
    parser.add_argument("--recalculate", default=False, action="store_true")
    parser.add_argument("--copy_cert", nargs="?", default=None)
    args = parser.parse_args()
    price = Price(args.cert, args.recalculate, args.copy_cert)
    price.act()
