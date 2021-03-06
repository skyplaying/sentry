import React from 'react';
import styled from '@emotion/styled';
import memoize from 'lodash/memoize';
import moment from 'moment';

import AsyncComponent from 'app/components/asyncComponent';
import Duration from 'app/components/duration';
import ErrorBoundary from 'app/components/errorBoundary';
import IdBadge from 'app/components/idBadge';
import Link from 'app/components/links/link';
import {PanelItem} from 'app/components/panels';
import TimeSince from 'app/components/timeSince';
import Tooltip from 'app/components/tooltip';
import {IconWarning} from 'app/icons';
import {t, tct} from 'app/locale';
import overflowEllipsis from 'app/styles/overflowEllipsis';
import space from 'app/styles/space';
import {Organization, Project} from 'app/types';
import {getUtcDateString} from 'app/utils/dates';
import getDynamicText from 'app/utils/getDynamicText';
import theme from 'app/utils/theme';
import {alertDetailsLink} from 'app/views/alerts/details';

import {
  API_INTERVAL_POINTS_LIMIT,
  API_INTERVAL_POINTS_MIN,
} from '../rules/details/constants';
import {Incident, IncidentStats, IncidentStatus} from '../types';
import {getIncidentMetricPreset, isIssueAlert} from '../utils';

import SparkLine from './sparkLine';
import {TableLayout, TitleAndSparkLine} from './styles';

/**
 * Retrieve the start/end for showing the graph of the metric
 * Will show at least 150 and no more than 10,000 data points
 */
export const makeRuleDetailsQuery = (
  incident: Incident
): {start: string; end: string} => {
  const {timeWindow} = incident.alertRule;
  const timeWindowMillis = timeWindow * 60 * 1000;
  const minRange = timeWindowMillis * API_INTERVAL_POINTS_MIN;
  const maxRange = timeWindowMillis * API_INTERVAL_POINTS_LIMIT;
  const now = moment.utc();
  const startDate = moment.utc(incident.dateStarted);
  // make a copy of now since we will modify endDate and use now for comparing
  const endDate = incident.dateClosed ? moment.utc(incident.dateClosed) : moment(now);
  const incidentRange = Math.max(endDate.diff(startDate), 3 * timeWindowMillis);
  const range = Math.min(maxRange, Math.max(minRange, incidentRange));
  const halfRange = moment.duration(range / 2);

  return {
    start: getUtcDateString(startDate.subtract(halfRange)),
    end: getUtcDateString(moment.min(endDate.add(halfRange), now)),
  };
};

type Props = {
  incident: Incident;
  projects: Project[];
  projectsLoaded: boolean;
  orgId: string;
  filteredStatus: 'open' | 'closed';
  organization: Organization;
} & AsyncComponent['props'];

type State = {
  stats: IncidentStats;
} & AsyncComponent['state'];

class AlertListRow extends AsyncComponent<Props, State> {
  get metricPreset() {
    const {incident} = this.props;
    return incident ? getIncidentMetricPreset(incident) : undefined;
  }

  getEndpoints(): ReturnType<AsyncComponent['getEndpoints']> {
    const {orgId, incident, filteredStatus} = this.props;

    if (filteredStatus === 'open') {
      return [
        ['stats', `/organizations/${orgId}/incidents/${incident.identifier}/stats/`],
      ];
    }

    return [];
  }

  /**
   * Memoized function to find a project from a list of projects
   */
  getProject = memoize((slug: string, projects: Project[]) =>
    projects.find(project => project.slug === slug)
  );

  renderLoading() {
    return this.renderBody();
  }

  renderError() {
    return this.renderBody();
  }

  renderTimeSince(date: string) {
    return (
      <CreatedResolvedTime>
        <TimeSince date={date} />
      </CreatedResolvedTime>
    );
  }

  renderStatusIndicator() {
    const {status} = this.props.incident;
    const isResolved = status === IncidentStatus.CLOSED;
    const isWarning = status === IncidentStatus.WARNING;

    const color = isResolved ? theme.gray200 : isWarning ? theme.orange300 : theme.red200;
    const text = isResolved ? t('Resolved') : isWarning ? t('Warning') : t('Critical');

    return (
      <Tooltip title={tct('Status: [text]', {text})}>
        <StatusIndicator color={color} />
      </Tooltip>
    );
  }

  renderBody() {
    const {
      incident,
      orgId,
      projectsLoaded,
      projects,
      filteredStatus,
      organization,
    } = this.props;
    const {error, stats} = this.state;
    const started = moment(incident.dateStarted);
    const duration = moment
      .duration(moment(incident.dateClosed || new Date()).diff(started))
      .as('seconds');
    const slug = incident.projects[0];

    const hasRedesign =
      !isIssueAlert(incident.alertRule) &&
      organization.features.includes('alert-details-redesign');

    const alertLink = hasRedesign
      ? {
          pathname: alertDetailsLink(organization, incident),
          query: {alert: incident.identifier},
        }
      : {
          pathname: `/organizations/${orgId}/alerts/${incident.identifier}/`,
        };

    return (
      <ErrorBoundary>
        <IncidentPanelItem>
          <TableLayout status={filteredStatus}>
            <TitleAndSparkLine status={filteredStatus}>
              <Title>
                {this.renderStatusIndicator()}
                <IncidentLink to={alertLink}>Alert #{incident.id}</IncidentLink>
                {incident.title}
              </Title>

              {filteredStatus === 'open' && (
                <SparkLine
                  error={error && <ErrorLoadingStatsIcon />}
                  eventStats={stats?.eventStats}
                />
              )}
            </TitleAndSparkLine>

            <ProjectBadge
              avatarSize={18}
              project={!projectsLoaded ? {slug} : this.getProject(slug, projects)}
            />

            {this.renderTimeSince(incident.dateStarted)}

            {filteredStatus === 'closed' && (
              <Duration seconds={getDynamicText({value: duration, fixed: 1200})} />
            )}

            {filteredStatus === 'closed' &&
              incident.dateClosed &&
              this.renderTimeSince(incident.dateClosed)}
          </TableLayout>
        </IncidentPanelItem>
      </ErrorBoundary>
    );
  }
}

function ErrorLoadingStatsIcon() {
  return (
    <Tooltip title={t('Error loading alert stats')}>
      <IconWarning />
    </Tooltip>
  );
}

const CreatedResolvedTime = styled('div')`
  ${overflowEllipsis}
  line-height: 1.4;
  display: flex;
  align-items: center;
`;

const ProjectBadge = styled(IdBadge)`
  flex-shrink: 0;
`;

const StatusIndicator = styled('div')<{color: string}>`
  width: 10px;
  height: 12px;
  background: ${p => p.color};
  display: inline-block;
  border-top-right-radius: 40%;
  border-bottom-right-radius: 40%;
  margin-bottom: -1px;
`;

const Title = styled('span')`
  ${overflowEllipsis}
`;

const IncidentLink = styled(Link)`
  padding: 0 ${space(1)};
`;

const IncidentPanelItem = styled(PanelItem)`
  font-size: ${p => p.theme.fontSizeMedium};
  padding: ${space(1.5)} ${space(2)} ${space(1.5)} 0;
`;

export default AlertListRow;
