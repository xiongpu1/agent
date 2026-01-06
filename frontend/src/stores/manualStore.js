import { reactive } from 'vue'

const manualState = reactive({
  productName: '',
  bomCode: '',
  bomType: '',
  createdAt: 0,
  productFiles: [],
  accessoryFiles: [],
  productOcrFiles: [],
  accessoryOcrFiles: [],
  productOcrGroups: [],
  accessoryOcrGroups: [],
  sessionId: '',
  ocrProgress: null
})

const revokeObjectUrls = (files = []) => {
  files.forEach((file) => {
    if (file?.previewUrl) {
      URL.revokeObjectURL(file.previewUrl)
    }
  })
}

const releaseAllObjectUrls = () => {
  revokeObjectUrls(manualState.productFiles)
  revokeObjectUrls(manualState.accessoryFiles)
  releaseOcrObjectUrls()
}

const releaseOcrObjectUrls = () => {
  revokeObjectUrls(manualState.productOcrFiles)
  revokeObjectUrls(manualState.accessoryOcrFiles)
}

export const useManualStore = () => manualState

export const setManualData = ({
  productName = '',
  bomCode = '',
  bomType = '',
  productFiles = [],
  accessoryFiles = [],
  productOcrFiles = [],
  accessoryOcrFiles = [],
  productOcrGroups = [],
  accessoryOcrGroups = [],
  sessionId = '',
  ocrProgress = null
} = {}) => {
  releaseAllObjectUrls()

  manualState.productName = productName
  manualState.bomCode = bomCode
  manualState.bomType = bomType
  manualState.productFiles = productFiles
  manualState.accessoryFiles = accessoryFiles
  manualState.productOcrFiles = productOcrFiles
  manualState.accessoryOcrFiles = accessoryOcrFiles
  manualState.productOcrGroups = productOcrGroups
  manualState.accessoryOcrGroups = accessoryOcrGroups
  manualState.sessionId = sessionId
  manualState.ocrProgress = ocrProgress
  manualState.createdAt = Date.now()
}

export const clearManualData = () => {
  setManualData({
    productName: '',
    bomCode: '',
    bomType: '',
    productFiles: [],
    accessoryFiles: [],
    productOcrFiles: [],
    accessoryOcrFiles: [],
    productOcrGroups: [],
    accessoryOcrGroups: [],
    sessionId: '',
    ocrProgress: null
  })
}

export const setManualOcrResults = ({
  productOcrFiles = [],
  accessoryOcrFiles = [],
  productOcrGroups = [],
  accessoryOcrGroups = []
} = {}) => {
  releaseOcrObjectUrls()
  manualState.productOcrFiles = productOcrFiles
  manualState.accessoryOcrFiles = accessoryOcrFiles
  manualState.productOcrGroups = productOcrGroups
  manualState.accessoryOcrGroups = accessoryOcrGroups
}

export const setManualSession = (sessionId = '') => {
  manualState.sessionId = sessionId
}

export const setManualOcrProgress = (progress = null) => {
  manualState.ocrProgress = progress
}
