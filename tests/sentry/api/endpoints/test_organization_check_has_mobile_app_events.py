from sentry.testutils import APITestCase


from sentry.utils.compat import mock
from sentry.utils.samples import create_sample_event


class OrganizationIntegrationRequestTest(APITestCase):
    endpoint = "sentry-api-0-organization-check-has-mobile-events"

    def setUp(self):
        super().setUp()
        self.project = self.create_project(organization=self.organization)
        self.login_as(user=self.user)

    def gen_event(self, browser_name):
        return create_sample_event(
            project=self.project, platform="python", contexts={"browser": {"name": browser_name}}
        )

    @mock.patch("sentry.api.endpoints.organization_check_has_mobile_app_events.cache.set")
    def test_basic(self, mock_cache_set):
        self.gen_event("okhttp")
        response = self.get_response(self.organization.slug, userAgents=["okhttp"])
        expected = {"browserName": "okhttp", "clientOsName": ""}
        assert response.status_code == 200
        assert response.data == expected
        mock_cache_set.assert_called_with(mock.ANY, {"result": expected}, 24 * 60 * 60)

    @mock.patch("sentry.api.endpoints.organization_check_has_mobile_app_events.discover.query")
    def test_hit_cache_on_success(self, mock_query):
        mock_query.return_value = {"data": [{"browser.name": "okhttp", "client_os_name": ""}]}
        response = self.get_response(self.organization.slug, userAgents=["okhttp"])
        assert response.status_code == 200
        assert response.data == {"browserName": "okhttp", "clientOsName": ""}
        assert mock_query.call_count == 1

        response = self.get_response(self.organization.slug, userAgents=["okhttp"])
        assert response.status_code == 200
        assert response.data == {"browserName": "okhttp", "clientOsName": ""}
        assert mock_query.call_count == 1

    def test_no_match(self):
        self.gen_event("Chrome")
        response = self.get_response(self.organization.slug, userAgents=["okhttp"])
        assert response.status_code == 200
        assert response.data is None

    @mock.patch("sentry.api.endpoints.organization_check_has_mobile_app_events.discover.query")
    def test_hit_cache_on_no_match(self, mock_query):
        mock_query.return_value = {"data": []}
        response = self.get_response(self.organization.slug, userAgents=["okhttp"])
        assert response.status_code == 200
        assert response.data is None
        assert mock_query.call_count == 1

        response = self.get_response(self.organization.slug, userAgents=["okhttp"])
        assert response.status_code == 200
        assert response.data is None
        assert mock_query.call_count == 1

    @mock.patch("sentry.api.endpoints.organization_check_has_mobile_app_events.discover.query")
    def test_cache_miss_different_org(self, mock_query):
        mock_query.return_value = {"data": []}
        response = self.get_response(self.organization.slug, userAgents=["okhttp"])
        assert response.status_code == 200
        assert mock_query.call_count == 1

        org2 = self.create_organization(owner=self.user)
        team = self.create_team(organization=org2)
        self.create_project(organization=org2, teams=[team])
        response = self.get_response(org2.slug, userAgents=["okhttp"])
        assert response.status_code == 200
        assert mock_query.call_count == 2