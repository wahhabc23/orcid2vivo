from unittest import TestCase
from orcid2vivo_app.utility import clean_orcid, is_valid_orcid, safe_get


class TestUtility(TestCase):
    def test_clean_orcid(self):
        orcid = '0000-0003-1527-0030'

        # Test with orcid.org prefix.
        self.assertEqual(clean_orcid('orcid.org/' + orcid), orcid)

        # Test with http://orcid.org prefix.
        self.assertEqual(clean_orcid('http://orcid.org/' + orcid), orcid)

        # Test without prefix.
        self.assertEqual(clean_orcid(orcid), orcid)

    def test_is_valid_orcid(self):
        self.assertTrue(is_valid_orcid("0000-0003-1527-0030"))
        self.assertTrue(is_valid_orcid("0000-0003-1527-003X"))
        self.assertFalse(is_valid_orcid("0000-0003-1527-00301"))
        self.assertFalse(is_valid_orcid("0000-0003-1527-003"))

    def test_safe_get(self):
        d = {"a": {"b": {"c": "value"}}}
        self.assertEqual(safe_get(d, "a", "b", "c"), "value")
        self.assertEqual(safe_get(d, "a", "b", "x"), None)
        self.assertEqual(safe_get(d, "a", "b", "x", default="default"), "default")
        
        # Test with None values
        d_with_none = {"a": {"b": None}}
        self.assertEqual(safe_get(d_with_none, "a", "b", "c"), None)
        self.assertEqual(safe_get(d_with_none, "a", "b", "c", default="default"), "default")
        
        # Test with missing intermediate keys
        self.assertEqual(safe_get(d, "x", "y", "z"), None)
        
        # Test with None dictionary
        self.assertEqual(safe_get(None, "a", "b"), None)
        
        # Test with non-dictionary intermediate value
        d_with_list = {"a": {"b": ["item1", "item2"]}}
        self.assertEqual(safe_get(d_with_list, "a", "b", "c"), None)
