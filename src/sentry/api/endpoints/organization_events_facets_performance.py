from collections import defaultdict

import sentry_sdk
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from sentry import features, tagstore
from sentry.api.bases import NoProjects, OrganizationEventsV2EndpointBase
from sentry.api.paginator import GenericOffsetPaginator
from sentry.snuba import discover


class OrganizationEventsFacetsPerformanceEndpoint(OrganizationEventsV2EndpointBase):
    def has_feature(self, organization, request):
        return features.has(
            "organizations:performance-tag-explorer", organization, actor=request.user
        )

    def get(self, request, organization):
        if not self.has_feature(organization, request):
            return Response(status=404)

        try:
            params = self.get_snuba_params(request, organization)
        except NoProjects:
            return Response([])

        aggregate_column = request.GET.get("aggregateColumn", "duration")
        orderby = request.GET.get("order", None)

        if len(params.get("project_id", [])) > 1:
            raise ParseError(detail="You cannot view facet performance for multiple projects.")

        def data_fn(offset, limit):
            with sentry_sdk.start_span(op="discover.endpoint", description="discover_query"):
                with self.handle_query_errors():
                    facets = discover.get_performance_facets(
                        query=request.GET.get("query"),
                        params=params,
                        referrer="api.organization-events-facets-performance.top-tags",
                        aggregate_column=aggregate_column,
                        orderby=orderby,
                        offset=offset,
                        limit=limit,
                    )
                with sentry_sdk.start_span(
                    op="discover.endpoint", description="populate_results"
                ) as span:
                    span.set_data("facet_count", len(facets or []))
                    resp = defaultdict(lambda: {"key": "", "value": {}})
                    for row in facets:
                        values = resp[row.key]
                        values["key"] = tagstore.get_standardized_key(row.key)
                        values["value"] = {
                            "name": tagstore.get_tag_value_label(row.key, row.value),
                            "value": row.value,
                            "count": row.count,
                            "frequency": row.frequency,
                            "aggregate": row.performance,
                            "comparison": row.comparison,
                            "sumdelta": row.sumdelta,
                        }
                return {"data": list(resp.values())}

        with self.handle_query_errors():
            return self.paginate(
                request=request,
                paginator=GenericOffsetPaginator(data_fn=data_fn),
                on_results=lambda results: self.handle_results_with_meta(
                    request, organization, params["project_id"], results
                ),
                default_per_page=5,
                max_per_page=5,
            )
