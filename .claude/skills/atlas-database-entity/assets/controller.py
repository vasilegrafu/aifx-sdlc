from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import StockInstrument

class StockInstrumentDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, stock_instrument_spec):
        StandardDbCtrl(session).save(stock_instrument_spec)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(StockInstrument, criteria, **assigns)
    
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(StockInstrument)\
                                      .all()
    
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_list(session, filtering_spec, sorting_spec):
        query = StandardDbCtrl(session).select(StockInstrument)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.all()
    
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_page(session, filtering_spec, sorting_spec, pagination_spec):
        query = StandardDbCtrl(session).select(StockInstrument)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.paginate_by_spec(pagination_spec)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(StockInstrument)\
                                        .filter(StockInstrument.id == id)\
                                        .one_or_none()
    
    @staticmethod
    @session_injector
    def get_by_ticker_symbol(session, ticker_symbol):
        return StandardDbCtrl(session).select(StockInstrument)\
                                        .filter(StockInstrument.ticker_symbol == ticker_symbol)\
                                        .one_or_none()
    @staticmethod
    @session_injector
    def get_by_ticker_symbols(session, ticker_symbols):
        return StandardDbCtrl(session).select(StockInstrument)\
                                        .filter(StockInstrument.ticker_symbol.in_(ticker_symbols))\
                                        .all()
       
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(StockInstrument)\
                                .delete()
        
    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(StockInstrument)\
                                .filter(StockInstrument.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ticker_symbol(session, ticker_symbol):
        StandardDbCtrl(session).select(StockInstrument)\
                                .filter(StockInstrument.ticker_symbol == ticker_symbol)\
                                .delete()
        
    @staticmethod
    @session_injector
    def delete_by_ticker_symbols(session, ticker_symbols):
        StandardDbCtrl(session).select(StockInstrument)\
                                .filter(StockInstrument.ticker_symbol.in_(ticker_symbols))\
                                .delete()
