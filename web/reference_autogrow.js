import { app } from '../../scripts/app.js'

const EXTENSION_NAME = 'H3Continuum.ReferenceAutogrow'
const TARGET_CLASSES = new Set([
  'H3ContinuumSamplerProduction',
  'H3ContinuumSamplerTimelineVideo'
])
const BASE_REFERENCE_INPUTS = 3
const MAX_REFERENCE_INPUTS = 8
const REFERENCE_NAME = /^reference_image_(\d+)$/

function referenceIndex(input) {
  const match = REFERENCE_NAME.exec(String(input?.name ?? ''))
  if (!match) return 0
  const index = Number(match[1])
  return Number.isInteger(index) && index >= 1 && index <= MAX_REFERENCE_INPUTS
    ? index
    : 0
}

function isConnected(input) {
  return input?.link != null
}

function referenceInputs(node) {
  const result = new Map()
  for (let slot = 0; slot < (node.inputs?.length ?? 0); slot += 1) {
    const input = node.inputs[slot]
    const index = referenceIndex(input)
    if (index) result.set(index, { input, slot })
  }
  return result
}

function addMissingReferenceInputs(node, refs, highest) {
  for (let index = BASE_REFERENCE_INPUTS + 1; index <= highest; index += 1) {
    if (refs.has(index)) continue
    node.addInput?.(`reference_image_${index}`, 'IMAGE')
    const added = node.inputs?.[node.inputs.length - 1]
    if (added) refs.set(index, { input: added, slot: node.inputs.length - 1 })
  }
}

function trimTrailingReferenceInputs(node, refs, desiredHighest) {
  for (let index = MAX_REFERENCE_INPUTS; index > desiredHighest; index -= 1) {
    const entry = refs.get(index)
    if (!entry || isConnected(entry.input)) continue
    // Dynamic reference inputs are appended, and only unlinked trailing sockets
    // are removed. removeInput owns LiteGraph's slot bookkeeping.
    const slot = node.inputs?.findIndex((input) => referenceIndex(input) === index) ?? -1
    if (slot >= 0) node.removeInput?.(slot)
    refs.delete(index)
  }
}

function updateReferenceInputs(node) {
  const state = node?.__h3ContinuumReferenceAutogrow
  if (!state || state.updating) return
  state.updating = true
  try {
    const refs = referenceInputs(node)
    let highestPresent = BASE_REFERENCE_INPUTS
    let highestConnected = 0
    for (const [index, entry] of refs) {
      highestPresent = Math.max(highestPresent, index)
      if (isConnected(entry.input)) highestConnected = Math.max(highestConnected, index)
    }

    // Preserve serialized dynamic sockets first, including any older workflow
    // that already reached ref 8. Then expose exactly one spare socket after
    // the highest connected reference, capped at eight.
    addMissingReferenceInputs(node, refs, highestPresent)
    const desiredHighest = Math.min(
      MAX_REFERENCE_INPUTS,
      Math.max(BASE_REFERENCE_INPUTS, highestConnected + 1)
    )
    addMissingReferenceInputs(node, refs, desiredHighest)
    trimTrailingReferenceInputs(node, refs, desiredHighest)
    node.setDirtyCanvas?.(true, true)
  } finally {
    state.updating = false
  }
}

function scheduleUpdate(node) {
  const state = node?.__h3ContinuumReferenceAutogrow
  if (!state || state.scheduled) return
  state.scheduled = true
  queueMicrotask(() => {
    if (!node.__h3ContinuumReferenceAutogrow) return
    state.scheduled = false
    updateReferenceInputs(node)
  })
}

function install(node) {
  if (!node || node.__h3ContinuumReferenceAutogrow) return
  const state = { updating: false, scheduled: false }
  node.__h3ContinuumReferenceAutogrow = state

  const previousConnectionsChange = node.onConnectionsChange
  node.onConnectionsChange = function (...args) {
    const result = previousConnectionsChange?.apply(this, args)
    scheduleUpdate(this)
    return result
  }

  const previousConfigure = node.onConfigure
  node.onConfigure = function (...args) {
    const result = previousConfigure?.apply(this, args)
    scheduleUpdate(this)
    return result
  }

  const previousRemoved = node.onRemoved
  node.onRemoved = function (...args) {
    delete this.__h3ContinuumReferenceAutogrow
    return previousRemoved?.apply(this, args)
  }

  scheduleUpdate(node)
}

app.registerExtension({
  name: EXTENSION_NAME,
  nodeCreated(node) {
    const type = String(node?.comfyClass || node?.type || '')
    if (!TARGET_CLASSES.has(type)) return
    install(node)
  }
})
