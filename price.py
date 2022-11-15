import argparse
import json
import math
from collections import defaultdict
from datetime import date

from collection import Collection


class Price:
    def __init__(self, cert, set_avg):
        self.cert = cert
        self.set_avg = set_avg
        self.collection = Collection()

    def check(self):
        self.card = self.collection.get(self.cert)
        price = self.card["selling"]["price"]
        if self.set_avg:
            self._set_price_to_avg()
        else:
            self._set_from_sales_data()

    def _set_price_to_avg(self):
        avg_price = self.card["sales_data"]["avg_price"]
        if avg_price > 0:
            overwrite = (
                input(
                    f"Are you sure you want to set the price to {avg_price} JPY? [Y/n]\n > "
                ).lower()
                == "y"
            )
            if overwrite:
                self.card["selling"]["price"] = avg_price
            else:
                raise Exception("Ending.")
        else:
            raise Exception(f"Card #{self.cert} does not have any pricing data.")

        print(f"Editing the price for card #{self.cert}")
        self.collection.update(self.cert, self.card)
        print(f"Card successfully updated (#{self.cert}).")

    def _set_from_sales_data(self):
        price = self.card["selling"]["price"]
        if price > 0:
            # price has been set before
            print(f"The price has already been set at {price} JPY.")
            overwrite = (
                input(
                    "Are you sure you want to overwrite the price? [Y/n]\n > "
                ).lower()
                == "y"
            )
            print(overwrite)
            if not overwrite:
                raise Exception("Ending.")

        print(f"Editing the price for card #{self.cert}")
        self._collect_prices()
        self._save()

    def _collect_prices(self):

        total_weight = 0
        prices = []
        prices_dict = defaultdict(lambda: defaultdict(list))
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
                    prices.append(adjusted_price * weight)
                    total_weight += weight
                    prices_dict[website][status].append(
                        {
                            "price": price,
                            "adjusted_price": adjusted_price,
                            "grade": grade,
                        }
                    )

                    print(
                        f"-> Logging a PSA {grade} at {price} JPY. Adjusted to {adjusted_price} (SF: {scale_factor:.02f})."
                    )

        if not prices:
            raise Exception("No prices were added.")

        avg_price = int(sum(prices) / total_weight)
        self.avg_price = avg_price
        self.sales_data = prices_dict

    def _get_scale_factor(self, website, status, grade):
        multipliers = {"base": 1.1, "grade": 0.7, "signed": 10}

        weightings = {
            "same_grade": 1.5,
            "ebay_selling": 1,
            "ebay_sold": 1.5,
            "mercari_selling": 2,
            "mercari_sold": 3,
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

        multiplier *= math.pow(multipliers["grade"], grade - card_grade)

        return multiplier, weighting

    def _save(self):
        okay = (
            input(
                f"\n\nWe have calculated a price of {self.avg_price} JPY - is this okay to set?\n[Y/n]\n > "
            ).lower()
            == "y"
        )
        self.card["sales_data"] = json.loads(json.dumps(self.sales_data))
        self.card["sales_data"]["avg_price"] = self.avg_price
        self.card["sales_data"]["last_updated"] = date.today().strftime("%Y-%m-%d")
        if okay:
            print(f"Updating selling price.")
            self.card["selling"]["price"] = self.avg_price
        self.collection.update(self.cert, self.card)
        print(f"Card successfully updated (#{self.cert}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cert")
    parser.add_argument("--set_avg", default=False, action="store_true")
    args = parser.parse_args()
    price = Price(args.cert, args.set_avg)
    price.check()
