import * as k8s from "@kubernetes/client-node";

const kc = new k8s.KubeConfig();
let loaded = false;
try {
  kc.loadFromCluster();
  loaded = true;
} catch {
  kc.loadFromDefault();
}

const coreV1 = kc.makeApiClient(k8s.CoreV1Api);
const appsV1 = kc.makeApiClient(k8s.AppsV1Api);
const networkingV1 = kc.makeApiClient(k8s.NetworkingV1Api);

function isNotFound(error) {
  return error?.response?.statusCode === 404;
}

function isConflict(error) {
  return error?.response?.statusCode === 409;
}

export function kubeLoadedFromCluster() {
  return loaded;
}

async function createOrReplace({
  create,
  read,
  replace,
  body,
  namespace,
}) {
  try {
    if (namespace) {
      return await create(namespace, body);
    }
    return await create(body);
  } catch (error) {
    if (!isConflict(error)) {
      throw error;
    }
  }

  const existing = namespace ? await read(body.metadata.name, namespace) : await read(body.metadata.name);
  const resourceVersion = existing.body?.metadata?.resourceVersion;
  const updated = {
    ...body,
    metadata: {
      ...body.metadata,
      resourceVersion,
    },
  };
  if (namespace) {
    return await replace(body.metadata.name, namespace, updated);
  }
  return await replace(body.metadata.name, updated);
}

export async function ensureNamespace(namespaceManifest) {
  try {
    await coreV1.createNamespace(namespaceManifest);
    return;
  } catch (error) {
    if (isConflict(error)) {
      return;
    }
    throw error;
  }
}

export async function ensureSecret(secretManifest) {
  await createOrReplace({
    create: coreV1.createNamespacedSecret.bind(coreV1),
    read: coreV1.readNamespacedSecret.bind(coreV1),
    replace: coreV1.replaceNamespacedSecret.bind(coreV1),
    body: secretManifest,
    namespace: secretManifest.metadata.namespace,
  });
}

export async function ensureConfigMap(configMapManifest) {
  await createOrReplace({
    create: coreV1.createNamespacedConfigMap.bind(coreV1),
    read: coreV1.readNamespacedConfigMap.bind(coreV1),
    replace: coreV1.replaceNamespacedConfigMap.bind(coreV1),
    body: configMapManifest,
    namespace: configMapManifest.metadata.namespace,
  });
}

export async function ensurePvc(pvcManifest) {
  await createOrReplace({
    create: coreV1.createNamespacedPersistentVolumeClaim.bind(coreV1),
    read: coreV1.readNamespacedPersistentVolumeClaim.bind(coreV1),
    replace: coreV1.replaceNamespacedPersistentVolumeClaim.bind(coreV1),
    body: pvcManifest,
    namespace: pvcManifest.metadata.namespace,
  });
}

export async function ensureDeployment(deploymentManifest) {
  await createOrReplace({
    create: appsV1.createNamespacedDeployment.bind(appsV1),
    read: appsV1.readNamespacedDeployment.bind(appsV1),
    replace: appsV1.replaceNamespacedDeployment.bind(appsV1),
    body: deploymentManifest,
    namespace: deploymentManifest.metadata.namespace,
  });
}

export async function ensureService(serviceManifest) {
  await createOrReplace({
    create: coreV1.createNamespacedService.bind(coreV1),
    read: coreV1.readNamespacedService.bind(coreV1),
    replace: coreV1.replaceNamespacedService.bind(coreV1),
    body: serviceManifest,
    namespace: serviceManifest.metadata.namespace,
  });
}

export async function ensureIngress(ingressManifest) {
  await createOrReplace({
    create: networkingV1.createNamespacedIngress.bind(networkingV1),
    read: networkingV1.readNamespacedIngress.bind(networkingV1),
    replace: networkingV1.replaceNamespacedIngress.bind(networkingV1),
    body: ingressManifest,
    namespace: ingressManifest.metadata.namespace,
  });
}

export async function readNamespace(name) {
  try {
    const res = await coreV1.readNamespace(name);
    return res.body;
  } catch (error) {
    if (isNotFound(error)) {
      return null;
    }
    throw error;
  }
}

export async function readSecret(name, namespace) {
  try {
    const res = await coreV1.readNamespacedSecret(name, namespace);
    return res.body;
  } catch (error) {
    if (isNotFound(error)) {
      return null;
    }
    throw error;
  }
}

export async function readConfigMap(name, namespace) {
  try {
    const res = await coreV1.readNamespacedConfigMap(name, namespace);
    return res.body;
  } catch (error) {
    if (isNotFound(error)) {
      return null;
    }
    throw error;
  }
}

export async function readPvc(name, namespace) {
  try {
    const res = await coreV1.readNamespacedPersistentVolumeClaim(name, namespace);
    return res.body;
  } catch (error) {
    if (isNotFound(error)) {
      return null;
    }
    throw error;
  }
}

export async function readDeployment(name, namespace) {
  try {
    const res = await appsV1.readNamespacedDeployment(name, namespace);
    return res.body;
  } catch (error) {
    if (isNotFound(error)) {
      return null;
    }
    throw error;
  }
}

export async function readService(name, namespace) {
  try {
    const res = await coreV1.readNamespacedService(name, namespace);
    return res.body;
  } catch (error) {
    if (isNotFound(error)) {
      return null;
    }
    throw error;
  }
}

export async function readIngress(name, namespace) {
  try {
    const res = await networkingV1.readNamespacedIngress(name, namespace);
    return res.body;
  } catch (error) {
    if (isNotFound(error)) {
      return null;
    }
    throw error;
  }
}

export async function listPods(namespace, labelSelector) {
  const res = await coreV1.listNamespacedPod(
    namespace,
    undefined,
    undefined,
    undefined,
    undefined,
    labelSelector,
  );
  return res.body.items ?? [];
}
