import { Octokit } from '@octokit/rest'

let connectionSettings: any;

async function getAccessToken() {
  if (
    connectionSettings &&
    connectionSettings.settings?.expires_at &&
    new Date(connectionSettings.settings.expires_at).getTime() > Date.now()
  ) {
    return connectionSettings.settings.access_token;
  }

  const hostname = process.env.REPLIT_CONNECTORS_HOSTNAME;
  const xReplitToken = process.env.REPL_IDENTITY
    ? 'repl ' + process.env.REPL_IDENTITY
    : process.env.WEB_REPL_RENEWAL
    ? 'depl ' + process.env.WEB_REPL_RENEWAL
    : null;

  if (!xReplitToken) {
    throw new Error('GitHub not available: X-Replit-Token not found. Please connect GitHub in the Replit integrations panel.');
  }

  const res = await fetch(
    'https://' + hostname + '/api/v2/connection?include_secrets=true&connector_names=github',
    {
      headers: {
        'Accept': 'application/json',
        'X-Replit-Token': xReplitToken
      }
    }
  );
  const data = await res.json();
  connectionSettings = data.items?.[0];

  if (!connectionSettings) {
    throw new Error('GitHub not connected. Please authorize the GitHub integration in the Replit integrations panel (click the puzzle piece icon in the sidebar).');
  }

  const accessToken =
    connectionSettings.settings?.access_token ||
    connectionSettings.settings?.oauth?.credentials?.access_token;

  if (!accessToken) {
    throw new Error('GitHub access token not found. The GitHub connection may need to be re-authorized.');
  }
  return accessToken;
}

export async function getUncachableGitHubClient() {
  const accessToken = await getAccessToken();
  return new Octokit({ auth: accessToken });
}
