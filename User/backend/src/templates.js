const APP_NAME = "openclaw";

const DEFAULT_DENY_COMMANDS = [
  "camera.snap",
  "camera.clip",
  "screen.record",
  "contacts.add",
  "calendar.add",
  "reminders.add",
  "sms.send",
];

export function buildOpenClawConfig({ basePath }) {
  const payload = {
    meta: {
      lastTouchedVersion: "2026.3.8",
      lastTouchedAt: new Date().toISOString(),
    },
    auth: {
      profiles: {
        "openai:default": {
          provider: "openai",
          mode: "api_key",
        },
      },
    },
    models: {
      mode: "merge",
      providers: {
        openai: {
          baseUrl: "https://api.openai.com/v1",
          api: "openai-completions",
          models: [
            {
              id: "gpt-4o",
              name: "GPT-4o",
              reasoning: false,
              input: ["text", "image"],
              contextWindow: 128000,
              maxTokens: 4096,
            },
          ],
        },
      },
    },
    agents: {
      defaults: {
        model: {
          primary: "openai/gpt-4o",
        },
        models: {
          "openai/gpt-4o": {
            alias: "GPT-4o",
          },
        },
        workspace: "/home/node/.openclaw/workspace",
        compaction: {
          mode: "safeguard",
        },
        maxConcurrent: 4,
        subagents: {
          maxConcurrent: 8,
        },
      },
    },
    tools: {
      profile: "coding",
      web: {
        search: {
          enabled: true,
          provider: "brave",
          apiKey: "",
        },
      },
    },
    messages: {
      ackReactionScope: "group-mentions",
    },
    commands: {
      native: "auto",
      nativeSkills: "auto",
      restart: true,
      ownerDisplay: "raw",
    },
    session: {
      dmScope: "per-channel-peer",
    },
    channels: {
      telegram: {
        enabled: true,
        dmPolicy: "pairing",
        botToken: "__TELEGRAM_BOT_TOKEN__",
        groupPolicy: "allowlist",
        streaming: "partial",
      },
    },
    gateway: {
      port: 18789,
      mode: "local",
      bind: "lan",
      auth: {
        mode: "token",
        token: "__GATEWAY_AUTH_TOKEN__",
      },
      controlUi: {
        basePath,
        allowedOrigins: ["*"],
      },
      tailscale: {
        mode: "off",
        resetOnExit: false,
      },
      nodes: {
        denyCommands: DEFAULT_DENY_COMMANDS,
      },
    },
    skills: {
      entries: {
        goplaces: {
          apiKey: "11",
        },
      },
    },
    plugins: {
      entries: {
        telegram: {
          enabled: true,
        },
      },
    },
  };

  return JSON.stringify(payload, null, 2);
}

export function buildNamespace({ name, labels }) {
  return {
    apiVersion: "v1",
    kind: "Namespace",
    metadata: {
      name,
      labels,
    },
  };
}

export function buildSecret({ name, namespace, labels, telegramBotToken, openaiApiKey, gatewayAuthToken }) {
  return {
    apiVersion: "v1",
    kind: "Secret",
    metadata: {
      name,
      namespace,
      labels,
    },
    type: "Opaque",
    stringData: {
      TELEGRAM_BOT_TOKEN: telegramBotToken,
      OPENAI_API_KEY: openaiApiKey,
      GATEWAY_AUTH_TOKEN: gatewayAuthToken,
    },
  };
}

export function buildConfigMap({ name, namespace, labels, basePath }) {
  return {
    apiVersion: "v1",
    kind: "ConfigMap",
    metadata: {
      name,
      namespace,
      labels,
    },
    data: {
      "openclaw.json": buildOpenClawConfig({ basePath }),
    },
  };
}

export function buildPvc({ name, namespace, labels, storageClassName, storage }) {
  const spec = {
    accessModes: ["ReadWriteOnce"],
    resources: {
      requests: {
        storage,
      },
    },
  };
  if (storageClassName) {
    spec.storageClassName = storageClassName;
  }
  return {
    apiVersion: "v1",
    kind: "PersistentVolumeClaim",
    metadata: {
      name,
      namespace,
      labels,
    },
    spec,
  };
}

export function buildDeployment({
  name,
  namespace,
  labels,
  secretName,
  configMapName,
  pvcDataName,
  pvcWorkspaceName,
  image,
}) {
  return {
    apiVersion: "apps/v1",
    kind: "Deployment",
    metadata: {
      name,
      namespace,
      labels,
    },
    spec: {
      replicas: 1,
      selector: {
        matchLabels: labels,
      },
      strategy: {
        type: "Recreate",
      },
      template: {
        metadata: {
          labels,
        },
        spec: {
          securityContext: {
            runAsUser: 1000,
            runAsGroup: 1000,
            fsGroup: 1000,
          },
          initContainers: [
            {
              name: "inject-secrets",
              image: "busybox:1.36",
              command: [
                "sh",
                "-c",
                [
                  "set -e",
                  "cp /config-template/openclaw.json /config-out/openclaw.json",
                  "sed -i \"s|__TELEGRAM_BOT_TOKEN__|$(cat /secrets/TELEGRAM_BOT_TOKEN)|g\" /config-out/openclaw.json",
                  "sed -i \"s|__GATEWAY_AUTH_TOKEN__|$(cat /secrets/GATEWAY_AUTH_TOKEN)|g\" /config-out/openclaw.json",
                  "echo \"Secret injection complete.\"",
                ].join("\n"),
              ],
              volumeMounts: [
                {
                  name: "config-template",
                  mountPath: "/config-template",
                  readOnly: true,
                },
                {
                  name: "secret-files",
                  mountPath: "/secrets",
                  readOnly: true,
                },
                {
                  name: "config-out",
                  mountPath: "/config-out",
                },
              ],
              securityContext: {
                runAsUser: 1000,
                runAsGroup: 1000,
                allowPrivilegeEscalation: false,
              },
            },
          ],
          containers: [
            {
              name: APP_NAME,
              image,
              imagePullPolicy: "Always",
              command: ["node", "openclaw.mjs", "gateway", "--bind", "lan"],
              ports: [
                {
                  name: "gateway",
                  containerPort: 18789,
                  protocol: "TCP",
                },
                {
                  name: "cdp-relay",
                  containerPort: 18792,
                  protocol: "TCP",
                },
              ],
              env: [
                {
                  name: "HOME",
                  value: "/home/node",
                },
                {
                  name: "OPENCLAW_BROWSER_DISABLE_GRAPHICS_FLAGS",
                  value: "true",
                },
                {
                  name: "PLAYWRIGHT_BROWSERS_PATH",
                  value: "/home/node/.cache/ms-playwright",
                },
                {
                  name: "NODE_OPTIONS",
                  value: "--max-old-space-size=2048",
                },
                {
                  name: "OPENAI_API_KEY",
                  valueFrom: {
                    secretKeyRef: {
                      name: secretName,
                      key: "OPENAI_API_KEY",
                    },
                  },
                },
              ],
              volumeMounts: [
                {
                  name: "openclaw-data",
                  mountPath: "/home/node/.openclaw",
                },
                {
                  name: "openclaw-workspace",
                  mountPath: "/home/node/.openclaw/workspace",
                },
                {
                  name: "config-out",
                  mountPath: "/home/node/.openclaw/openclaw.json",
                  subPath: "openclaw.json",
                },
              ],
              resources: {
                requests: {
                  cpu: "500m",
                  memory: "1Gi",
                },
                limits: {
                  cpu: "2000m",
                  memory: "4Gi",
                },
              },
              securityContext: {
                allowPrivilegeEscalation: false,
                capabilities: {
                  add: ["SYS_ADMIN"],
                  drop: ["ALL"],
                },
              },
              livenessProbe: {
                exec: {
                  command: [
                    "sh",
                    "-c",
                    "wget -qO- --header=\"Authorization: Bearer $(cat /secrets/GATEWAY_AUTH_TOKEN)\" http://localhost:18789/health || exit 1",
                  ],
                },
                initialDelaySeconds: 30,
                periodSeconds: 30,
                failureThreshold: 3,
                timeoutSeconds: 10,
              },
              readinessProbe: {
                exec: {
                  command: [
                    "sh",
                    "-c",
                    "wget -qO- --header=\"Authorization: Bearer $(cat /secrets/GATEWAY_AUTH_TOKEN)\" http://localhost:18789/health || exit 1",
                  ],
                },
                initialDelaySeconds: 15,
                periodSeconds: 10,
                failureThreshold: 3,
                timeoutSeconds: 5,
              },
            },
          ],
          volumes: [
            {
              name: "config-template",
              configMap: {
                name: configMapName,
              },
            },
            {
              name: "secret-files",
              secret: {
                secretName: secretName,
              },
            },
            {
              name: "config-out",
              emptyDir: {},
            },
            {
              name: "openclaw-data",
              persistentVolumeClaim: {
                claimName: pvcDataName,
              },
            },
            {
              name: "openclaw-workspace",
              persistentVolumeClaim: {
                claimName: pvcWorkspaceName,
              },
            },
          ],
          terminationGracePeriodSeconds: 60,
        },
      },
    },
  };
}

export function buildService({ name, namespace, labels }) {
  return {
    apiVersion: "v1",
    kind: "Service",
    metadata: {
      name,
      namespace,
      labels,
    },
    spec: {
      type: "ClusterIP",
      selector: labels,
      ports: [
        {
          name: "gateway",
          port: 18789,
          targetPort: "gateway",
          protocol: "TCP",
        },
        {
          name: "cdp-relay",
          port: 18792,
          targetPort: "cdp-relay",
          protocol: "TCP",
        },
      ],
    },
  };
}

export function buildIngress({ name, namespace, labels, serviceName, basePath, ingressClassName }) {
  const spec = {
    rules: [
      {
        http: {
          paths: [
            {
              path: basePath,
              pathType: "Prefix",
              backend: {
                service: {
                  name: serviceName,
                  port: {
                    name: "gateway",
                  },
                },
              },
            },
          ],
        },
      },
    ],
  };
  if (ingressClassName) {
    spec.ingressClassName = ingressClassName;
  }
  return {
    apiVersion: "networking.k8s.io/v1",
    kind: "Ingress",
    metadata: {
      name,
      namespace,
      labels,
    },
    spec,
  };
}

export function buildLabels({ instanceId }) {
  return {
    "app.kubernetes.io/name": APP_NAME,
    "app.kubernetes.io/part-of": "openclaw",
    "app.kubernetes.io/instance": instanceId,
  };
}
