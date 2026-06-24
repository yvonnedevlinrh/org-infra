// Self-hosted Renovate configuration for complytime org.
// Manages Go toolchain patch updates across Go repositories.
// Preset rules are defined in go-toolchain-patches.json.
module.exports = {
  platform: 'github',
  onboarding: false,
  requireConfig: 'optional',
  repositories: [
    'complytime/complyctl',
    'complytime/complytime',
    'complytime/complytime-providers',
    'complytime/complytime-collector-components',
  ],
  globalExtends: [
    'github>complytime/org-infra:go-toolchain-patches',
  ],
};
