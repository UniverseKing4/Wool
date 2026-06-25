from wool.config import WoolConfig, ProviderConfig

c = WoolConfig()
c.add_provider(ProviderConfig(name="test_p1", base_url="...", api_key="..."))
c.add_provider(ProviderConfig(name="test_p2", base_url="...", api_key="..."))
c.active_provider = "test_p1"
c.save()

print("Initial:")
c = WoolConfig.load()
print(c)
