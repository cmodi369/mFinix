from mFinix.core.data_processing import prepare_transactions_data
from mFinix.core.xirr_calculation import calculate_stock_xirr_from_transactions


def run_once(method):
    """Decorator to ensure a method can only be executed once."""
    method._has_run = False

    def wrapper(self, *args, **kwargs):
        if method._has_run:
            return
        method._has_run = True
        return method(self, *args, **kwargs)

    return wrapper


def prepare_stocks_tab_data():
    ret_data_dict = {}
    ret_data_dict["transactions_data"] = prepare_transactions_data()
    stocks_xirr_data_dict = calculate_stock_xirr_from_transactions(
        ret_data_dict["transactions_data"]
    )
    ret_data_dict.update(stocks_xirr_data_dict)

    return ret_data_dict
