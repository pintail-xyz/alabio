from assetregister import AssetRegister

ar = AssetRegister()
ar.add_all_assets()
ar.export_token_info()
ar.blocktimes.update()
ar.blocktimes.save()
for sym, adr in ar.token_lookup.items():
    print(f"calculating price history for {sym}")
    ar.calculate_price_history_in_eth(sym)
    ar.save_price_history(sym)
