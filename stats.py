import numpy as np

from collection import Collection


class Stats:
    def __init__(self):
        self.collection = Collection()
        self.collection.validate()

    def calculate(self):
        data = self.collection.data
        amount = len(data)

        # Number currently for sale
        selling = {}
        for cert, card in data.items():
            if "selling" in card and card["selling"]["price"] != 0:
                selling[cert] = card

        selling_prices = [card["selling"]["price"] for card in selling.values()]
        selling_stats = {
            "amount": len(selling),
            "max_price": max(selling_prices),
            "min_price": min(selling_prices),
            "avg_price": np.mean(selling_prices).astype(np.int32),
            "std_price": np.std(selling_prices).astype(np.int32),
        }

        estimated_collection_price = int(amount * selling_stats["avg_price"])
        print(
            f"The estimated price of the collection is {estimated_collection_price} JPY."
        )

        print(
            f"Currently {selling_stats['amount']}/{amount} ({selling_stats['amount']/amount*100:.02f}%) of the collection is up for sale."
        )


if __name__ == "__main__":
    Stats().calculate()
