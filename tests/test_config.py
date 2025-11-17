"""Tests for configuration module."""

from ontario_data.config import OntarioConfig


class TestOntarioConfig:
    """Tests for OntarioConfig dataclass."""

    def test_default_values(self):
        """Test that OntarioConfig has correct default values."""
        config = OntarioConfig()

        assert config.ebird_api_key is None
        assert config.datastream_api_key is None
        assert config.inat_rate_limit == 60
        assert config.cache_ttl_hours == 24

    def test_with_ebird_key(self):
        """Test creating config with eBird API key."""
        config = OntarioConfig(ebird_api_key="test-key-123")

        assert config.ebird_api_key == "test-key-123"
        assert config.datastream_api_key is None
        assert config.inat_rate_limit == 60
        assert config.cache_ttl_hours == 24

    def test_with_all_parameters(self):
        """Test creating config with all parameters specified."""
        config = OntarioConfig(
            ebird_api_key="ebird-key",
            datastream_api_key="datastream-key",
            inat_rate_limit=100,
            cache_ttl_hours=12,
        )

        assert config.ebird_api_key == "ebird-key"
        assert config.datastream_api_key == "datastream-key"
        assert config.inat_rate_limit == 100
        assert config.cache_ttl_hours == 12

    def test_custom_rate_limit(self):
        """Test creating config with custom rate limit."""
        config = OntarioConfig(inat_rate_limit=30)

        assert config.inat_rate_limit == 30
        assert config.cache_ttl_hours == 24

    def test_custom_cache_ttl(self):
        """Test creating config with custom cache TTL."""
        config = OntarioConfig(cache_ttl_hours=48)

        assert config.cache_ttl_hours == 48
        assert config.inat_rate_limit == 60

    def test_is_dataclass(self):
        """Test that OntarioConfig is a dataclass."""
        config = OntarioConfig()
        assert hasattr(config, "__dataclass_fields__")
