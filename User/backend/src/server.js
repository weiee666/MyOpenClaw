import crypto from "node:crypto";
import express from "express";
import cors from "cors";
import {
  ensureConfigMap,
  ensureDeployment,
  ensureIngress,
  ensureNamespace,
  ensurePvc,
  ensureSecret,
  ensureService,
  kubeLoadedFromCluster,
  listPods,
  readConfigMap,
  readDeployment,
  readIngress,
  readNamespace,
  readPvc,
  readSecret,
  readService,
} from "./k8s.js";
import {
  buildConfigMap,
  buildDeployment,
  buildIngress,
  buildLabels,
  buildNamespace,
  buildPvc,
  buildSecret,
  buildService,
} from "./templates.js";
import { buildName, ensureToken, normalizeUserId } from "./validation.js";

const PORT = Number.parseInt(process.env.PORT ?? "4000", 10);
const IMAGE = process.env.OPENCLAW_IMAGE ?? "weiee666/myopenclaw:latest";
const STORAGE_CLASS = process.env.OPENCLAW_STORAGE_CLASS ?? "";
const INGRESS_CLASS = process.env.OPENCLAW_INGRESS_CLASS ?? "";
const BASE_PATH_PREFIX = "/user";

const app = express();
app.use(cors({ origin: true }));
app.use(express.json({ limit: "1mb" }));

function buildResourceNames(instanceId) {
  const namespace = buildName("openclaw-user-", instanceId);
  const suffix = namespace.replace(/^openclaw-user-/, "");
  return {
    id: suffix,
    namespace,
    configMap: buildName("openclaw-config-", suffix),
    secret: buildName("openclaw-secrets-", suffix),
    pvcData: buildName("openclaw-data-", suffix),
    pvcWorkspace: buildName("openclaw-workspace-", suffix),
    deployment: buildName("openclaw-", suffix),
    service: buildName("openclaw-gateway-", suffix),
    ingress: buildName("openclaw-gateway-", suffix),
  };
}

function buildAccessPath(instanceId) {
  return `${BASE_PATH_PREFIX}/${instanceId}`;
}

function makeGatewayToken() {
  return crypto.randomBytes(24).toString("hex");
}

function decodeSecretValue(secret, key) {
  const value = secret?.data?.[key];
  if (!value) {
    return null;
  }
  return Buffer.from(value, "base64").toString("utf8");
}

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, inCluster: kubeLoadedFromCluster() });
});

app.post("/api/pods", async (req, res) => {
  try {
    const rawUserId = req.body?.userId;
    const telegramBotToken = ensureToken("telegramBotToken", req.body?.telegramBotToken);
    const openaiApiKey = ensureToken("openaiApiKey", req.body?.openaiApiKey);
    const instanceId = normalizeUserId(rawUserId);
    const names = buildResourceNames(instanceId);
    const basePath = buildAccessPath(names.id);
    const labels = buildLabels({ instanceId: names.id });
    const gatewayAuthToken = makeGatewayToken();

    const namespaceManifest = buildNamespace({
      name: names.namespace,
      labels,
    });
    const secretManifest = buildSecret({
      name: names.secret,
      namespace: names.namespace,
      labels,
      telegramBotToken,
      openaiApiKey,
      gatewayAuthToken,
    });
    const configMapManifest = buildConfigMap({
      name: names.configMap,
      namespace: names.namespace,
      labels,
      basePath,
    });
    const pvcDataManifest = buildPvc({
      name: names.pvcData,
      namespace: names.namespace,
      labels,
      storageClassName: STORAGE_CLASS || undefined,
      storage: "5Gi",
    });
    const pvcWorkspaceManifest = buildPvc({
      name: names.pvcWorkspace,
      namespace: names.namespace,
      labels,
      storageClassName: STORAGE_CLASS || undefined,
      storage: "20Gi",
    });
    const deploymentManifest = buildDeployment({
      name: names.deployment,
      namespace: names.namespace,
      labels,
      secretName: names.secret,
      configMapName: names.configMap,
      pvcDataName: names.pvcData,
      pvcWorkspaceName: names.pvcWorkspace,
      image: IMAGE,
    });
    const serviceManifest = buildService({
      name: names.service,
      namespace: names.namespace,
      labels,
    });
    const ingressManifest = buildIngress({
      name: names.ingress,
      namespace: names.namespace,
      labels,
      serviceName: names.service,
      basePath,
      ingressClassName: INGRESS_CLASS || undefined,
    });

    await ensureNamespace(namespaceManifest);
    await ensureSecret(secretManifest);
    await ensureConfigMap(configMapManifest);
    await ensurePvc(pvcDataManifest);
    await ensurePvc(pvcWorkspaceManifest);
    await ensureDeployment(deploymentManifest);
    await ensureService(serviceManifest);
    await ensureIngress(ingressManifest);

    res.json({
      id: names.id,
      namespace: names.namespace,
      accessPath: basePath,
      gatewayAuthToken,
    });
  } catch (error) {
    res.status(400).json({
      error: error instanceof Error ? error.message : "Failed to create pod",
    });
  }
});

app.get("/api/pods/:id/status", async (req, res) => {
  try {
    const instanceId = normalizeUserId(req.params.id);
    const names = buildResourceNames(instanceId);
    const basePath = buildAccessPath(names.id);

    const [
      namespace,
      secret,
      configMap,
      pvcData,
      pvcWorkspace,
      deployment,
      service,
      ingress,
    ] = await Promise.all([
      readNamespace(names.namespace),
      readSecret(names.secret, names.namespace),
      readConfigMap(names.configMap, names.namespace),
      readPvc(names.pvcData, names.namespace),
      readPvc(names.pvcWorkspace, names.namespace),
      readDeployment(names.deployment, names.namespace),
      readService(names.service, names.namespace),
      readIngress(names.ingress, names.namespace),
    ]);

    const steps = [
      { name: "namespace", ok: Boolean(namespace), details: namespace ? "ready" : "missing" },
      { name: "secret", ok: Boolean(secret), details: secret ? "ready" : "missing" },
      { name: "configmap", ok: Boolean(configMap), details: configMap ? "ready" : "missing" },
      {
        name: "pvc-data",
        ok: pvcData?.status?.phase === "Bound",
        details: pvcData?.status?.phase ?? "pending",
      },
      {
        name: "pvc-workspace",
        ok: pvcWorkspace?.status?.phase === "Bound",
        details: pvcWorkspace?.status?.phase ?? "pending",
      },
      {
        name: "deployment",
        ok: (deployment?.status?.availableReplicas ?? 0) >= 1,
        details: deployment?.status?.availableReplicas ? "available" : "pending",
      },
      { name: "service", ok: Boolean(service), details: service ? "ready" : "missing" },
      { name: "ingress", ok: Boolean(ingress), details: ingress ? "ready" : "missing" },
    ].map((step) => ({
      name: step.name,
      status: step.ok ? "ready" : "pending",
      details: step.details,
    }));

    const pods = await listPods(
      names.namespace,
      `app.kubernetes.io/name=openclaw,app.kubernetes.io/instance=${names.id}`,
    );
    const pod = pods[0];
    const podPhase = pod?.status?.phase ?? "Pending";
    const ready = steps.every((step) => step.status === "ready") && podPhase === "Running";

    res.json({
      id: names.id,
      namespace: names.namespace,
      accessPath: basePath,
      steps,
      podPhase,
      ready,
    });
  } catch (error) {
    res.status(400).json({
      error: error instanceof Error ? error.message : "Failed to read status",
    });
  }
});

app.get("/api/pods/:id/secret", async (req, res) => {
  try {
    const instanceId = normalizeUserId(req.params.id);
    const names = buildResourceNames(instanceId);
    const secret = await readSecret(names.secret, names.namespace);
    if (!secret) {
      res.status(404).json({ error: "Secret not found" });
      return;
    }
    const gatewayAuthToken = decodeSecretValue(secret, "GATEWAY_AUTH_TOKEN");
    if (!gatewayAuthToken) {
      res.status(404).json({ error: "Gateway token not found" });
      return;
    }
    res.json({ gatewayAuthToken });
  } catch (error) {
    res.status(400).json({
      error: error instanceof Error ? error.message : "Failed to read secret",
    });
  }
});

app.listen(PORT, () => {
  console.log(`openclaw user backend listening on ${PORT}`);
});
