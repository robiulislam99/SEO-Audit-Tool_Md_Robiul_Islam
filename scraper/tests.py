from django.test import SimpleTestCase

from .checks import check_meta_description, check_title
from .scoring import build_seo_report


class SeoChecksTest(SimpleTestCase):
	def test_title_length_requires_50_to_60_chars(self):
		short_title = check_title({"title": "Short title"})
		valid_title = check_title({"title": "SEO audit tool for better rankings and visibility!"})

		self.assertEqual(short_title["severity"], "warning")
		self.assertEqual(valid_title["severity"], "pass")

	def test_meta_description_requires_150_to_160_chars(self):
		short_desc = check_meta_description({"meta_description": "Too short"})
		valid_desc = check_meta_description({"meta_description": "This meta description is intentionally written to be long enough for search engines while still staying within the preferred range for the page, now!s"})

		self.assertEqual(short_desc["severity"], "warning")
		self.assertEqual(valid_desc["severity"], "pass")

	def test_structured_report_includes_keyword_and_link_summaries(self):
		page_data = {
			"url": "https://example.com",
			"final_url": "https://example.com",
			"title": "SEO audit tool for better rankings and visibility!",
			"meta_description": "This meta description is intentionally written to be long enough for search engines while still staying within the preferred range for the page, now!s",
			"h1_tags": ["Example heading"],
			"h2_tags": ["Section heading"],
			"images": [{"src": "https://example.com/image.jpg", "alt": "Example", "natural_width": 800, "natural_height": 600, "client_width": 400, "client_height": 300}],
			"links": {"internal": ["https://example.com/about"], "external": ["https://external.example.com"]},
			"links_with_text": [{"url": "https://example.com/about", "text": "About us"}],
			"body_text": "Example body copy with example keyword repeated. Example keyword appears twice.",
			"canonical_url": "https://example.com",
			"robots_meta": None,
			"googlebot_meta": None,
			"robots_header": None,
			"og_tags": {"og:title": "Example", "og:description": "Example", "og:image": "https://example.com/image.jpg"},
			"twitter_tags": {"twitter:card": "summary_large_image"},
			"structured_data": [],
			"load_time_ms": 1200,
			"dom_content_loaded_ms": 800,
			"request_count": 18,
			"page_size_bytes": 100000,
		}

		report = build_seo_report(page_data, target_keyword="example keyword", should_check_broken_links=False)

		self.assertIn("content_quality", report)
		self.assertIn("link_analysis", report)
		self.assertIn("image_optimization", report)
		self.assertEqual(report["performance"]["request_count"], 18)
		self.assertTrue(report["content_quality"]["top_keywords"])
		self.assertIn("internal_count", report["link_analysis"])
