from collections import defaultdict
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional, Set

from django.db.models import Count

from sentry.db.models.query import in_iexact
from sentry.models import (
    Activity,
    Commit,
    CommitFileChange,
    Deploy,
    Environment,
    EventError,
    Group,
    GroupLink,
    Organization,
    Project,
    ProjectTeam,
    Release,
    ReleaseCommit,
    Repository,
    User,
    UserEmail,
)


def get_projects(projects: Iterable[Project], team_ids: Iterable[int]) -> Set[Project]:
    team_projects = set(
        ProjectTeam.objects.filter(team_id__in=team_ids)
        .values_list("project_id", flat=True)
        .distinct()
    )
    return {p for p in projects if p.id in team_projects}


def get_users_by_teams(organization: Organization) -> Mapping[int, List[int]]:
    user_teams: MutableMapping[int, List[int]] = defaultdict(list)
    queryset = User.objects.filter(
        sentry_orgmember_set__organization_id=organization.id
    ).values_list("id", "sentry_orgmember_set__teams")
    for user_id, team_id in queryset:
        user_teams[user_id].append(team_id)
    return user_teams


def get_deploy(activity: Activity) -> Optional[Deploy]:
    try:
        return Deploy.objects.get(id=activity.data["deploy_id"])
    except Deploy.DoesNotExist:
        return None


def get_release(activity: Activity, organization: Organization) -> Optional[Release]:
    try:
        return Release.objects.get(
            organization_id=organization.id, version=activity.data["version"]
        )
    except Release.DoesNotExist:
        return None


def get_group_counts_by_project(
    release: Release, projects: Iterable[Project]
) -> Mapping[Project, int]:
    return dict(
        Group.objects.filter(
            project__in=projects,
            id__in=GroupLink.objects.filter(
                linked_type=GroupLink.LinkedType.commit,
                linked_id__in=ReleaseCommit.objects.filter(release=release).values_list(
                    "commit_id", flat=True
                ),
            ).values_list("group_id", flat=True),
        )
        .values_list("project")
        .annotate(num_groups=Count("id"))
    )


def get_users_by_emails(emails: Iterable[str], organization: Organization) -> Mapping[str, User]:
    if not emails:
        return {}

    return {
        ue.email: ue.user
        for ue in UserEmail.objects.filter(
            in_iexact("email", emails),
            is_verified=True,
            user__sentry_orgmember_set__organization=organization,
        ).select_related("user")
    }


def get_repos(
    commits: Iterable[Commit], users_by_email: Mapping[str, User], organization: Organization
) -> Iterable[Mapping[str, Any]]:
    repos = {
        r_id: {"name": r_name, "commits": []}
        for r_id, r_name in Repository.objects.filter(
            organization_id=organization.id,
            id__in={c.repository_id for c in commits},
        ).values_list("id", "name")
    }
    for commit in commits:
        user_option = users_by_email.get(commit.author.email) if commit.author_id else None
        repos[commit.repository_id]["commits"].append((commit, user_option))

    return list(repos.values())


def get_commits_for_release(release: Release) -> Set[Commit]:
    return {
        rc.commit
        for rc in ReleaseCommit.objects.filter(release=release).select_related(
            "commit", "commit__author"
        )
    }


def get_environment_for_deploy(deploy: Optional[Deploy]) -> str:
    if deploy:
        environment = Environment.objects.get(id=deploy.environment_id)
        if environment and environment.name:
            return str(environment.name)
    return "Default Environment"


def get_file_count(commits: Iterable[Commit], organization: Organization) -> int:
    return int(
        CommitFileChange.objects.filter(commit__in=commits, organization_id=organization.id)
        .values("filename")
        .distinct()
        .count()
    )


def summarize_issues(issues: Iterable[Any]) -> Iterable[Mapping[str, str]]:
    rv = []
    for issue in issues:
        extra_info = None
        msg_d = dict(issue["data"])
        msg_d["type"] = issue["type"]

        if "image_path" in issue["data"]:
            extra_info = issue["data"]["image_path"].rsplit("/", 1)[-1]
            if "image_arch" in issue["data"]:
                extra_info = "{} ({})".format(extra_info, issue["data"]["image_arch"])

        rv.append({"message": EventError(msg_d).message, "extra_info": extra_info})
    return rv
