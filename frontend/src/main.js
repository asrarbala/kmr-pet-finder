import './style.css'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const petsElement = document.querySelector('#pets')
const messageElement = document.querySelector('#message')
const refreshButton = document.querySelector('#refresh-button')
const browseSection = document.querySelector('#browse-section')
const ownedSection = document.querySelector('#owned-section')
const ownedHeading = document.querySelector('#owned-heading')
const ownedPetsElement = document.querySelector('#owned-pets')
const ownedMessageElement = document.querySelector('#owned-message')
const ownedRefreshButton = document.querySelector('#owned-refresh-button')
const viewOwnedButton = document.querySelector('#view-owned-button')
const reportSection = document.querySelector('#report-section')
const reportHeading = document.querySelector('#report-heading')
const reportForm = document.querySelector('#report-form')
const dateFields = ['day', 'month', 'year'].map((part) => document.querySelector(`#event-${part}`))
const dateWrap = document.querySelector('.date-input-wrap')
const calendarButton = document.querySelector('#date-picker-button')
const calendar = document.querySelector('#date-calendar')
const calendarMonth = document.querySelector('#calendar-month')
const calendarDays = document.querySelector('#calendar-days')
const formError = document.querySelector('#form-error')
const submitButton = document.querySelector('#submit-button')
const newReportButton = document.querySelector('#new-report-button')
const backButton = document.querySelector('#back-button')
const resultPanel = document.querySelector('#result-panel')
const resultMessage = document.querySelector('#result-message')
const retryPhotoButton = document.querySelector('#retry-photo-button')
const retryPhotoField = document.querySelector('#retry-photo-field')
const retryPhotoInput = document.querySelector('#retry-photo-input')

const maxPhotoBytes = 5 * 1024 * 1024
const allowedPhotoTypes = ['image/jpeg', 'image/png', 'image/webp']
const requiredTextFields = ['species', 'description', 'area', 'district', 'contact_name', 'contact_phone']
const fieldNames = {
  status: 'Status', species: 'Species', breed: 'Breed', pet_name: 'Pet name',
  description: 'Description', area: 'Area', district: 'District', event_date: 'Date',
  contact_name: 'Contact name', contact_phone: 'Contact phone', contact_email: 'Contact email',
}

let pendingPhoto = null
let accessSaved = true
let shownMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1)

// Kept per pet so a later edit/delete screen can find this browser's private access.
function editTokenKey(id) {
  return `kmr-pet-finder:pet:${id}:edit-token`
}

function ownedReportIds() {
  const ids = []
  try {
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index)
      const match = /^kmr-pet-finder:pet:(\d+):edit-token$/.exec(key)
      if (match && localStorage.getItem(key)) ids.push(Number(match[1]))
    }
  } catch {
    return []
  }
  return [...new Set(ids)]
}

function updateOwnedAction() {
  viewOwnedButton.hidden = ownedReportIds().length === 0
}

function displayDate(isoDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate || '')
  return match ? `${match[3]}/${match[2]}/${match[1]}` : isoDate || ''
}

function apiDate(displayValue) {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(displayValue.trim())
  if (!match) return null

  const day = Number(match[1])
  const month = Number(match[2])
  const year = Number(match[3])
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth[month - 1]) return null
  return `${match[3]}-${match[2]}-${match[1]}`
}

function selectedDate() {
  return apiDate(dateFields.map((field) => field.value).join('/'))
}

function todayIndiaIso() {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

function setDateFields(isoDate) {
  const parts = isoDate ? displayDate(isoDate).split('/') : []
  dateFields.forEach((field, index) => {
    field.value = parts[index] || ''
    field.setCustomValidity('')
  })
}

function renderCalendar() {
  const year = shownMonth.getFullYear()
  const month = shownMonth.getMonth()
  const selected = selectedDate()
  const today = todayIndiaIso()
  calendarMonth.textContent = new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric' }).format(shownMonth)
  document.querySelector('#calendar-next').disabled = `${year}-${String(month + 1).padStart(2, '0')}` >= today.slice(0, 7)

  const cells = Array.from({ length: shownMonth.getDay() }, () => {
    const blank = document.createElement('span')
    blank.setAttribute('aria-hidden', 'true')
    return blank
  })
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  for (let day = 1; day <= daysInMonth; day += 1) {
    const button = document.createElement('button')
    const date = new Date(year, month, day)
    const isoDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    button.type = 'button'
    button.textContent = String(day)
    button.dataset.date = isoDate
    button.setAttribute('aria-label', new Intl.DateTimeFormat('en-IN', { dateStyle: 'full' }).format(date))
    button.setAttribute('aria-pressed', String(isoDate === selected))
    button.disabled = isoDate > today
    if (isoDate === today) button.classList.add('today')
    cells.push(button)
  }
  calendarDays.replaceChildren(...cells)
}

function positionCalendar() {
  if (calendar.hidden) return
  const field = dateWrap.getBoundingClientRect()
  const gap = 8
  const edge = 8
  calendar.style.maxHeight = ''
  const popupHeight = calendar.scrollHeight
  const above = Math.max(0, field.top - gap - edge)
  const below = Math.max(0, window.innerHeight - field.bottom - gap - edge)
  const openBelow = below >= popupHeight || below >= above
  const available = openBelow ? below : above
  calendar.style.maxHeight = `${available}px`
  calendar.style.top = `${openBelow ? field.bottom + gap : field.top - gap - Math.min(popupHeight, available)}px`
  calendar.style.left = `${Math.max(edge, Math.min(field.left, window.innerWidth - calendar.offsetWidth - edge))}px`
}

function closeCalendar() {
  calendar.hidden = true
  calendarButton.setAttribute('aria-expanded', 'false')
}

function makeElement(tag, className, text) {
  const element = document.createElement(tag)
  if (className) element.className = className
  if (text) element.textContent = text
  return element
}

function photoSource(photoUrl) {
  if (!photoUrl) return null
  try {
    const url = new URL(photoUrl, `${apiBaseUrl}/`)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null
  } catch {
    return null
  }
}

function petCard(post) {
  const card = makeElement('article', 'pet-card')
  const photo = photoSource(post.photo_url)

  if (photo) {
    const image = makeElement('img', 'pet-photo')
    image.src = photo
    image.alt = post.pet_name ? `Photo of ${post.pet_name}` : `Photo of a ${post.species}`
    image.loading = 'lazy'
    card.append(image)
  } else {
    card.append(makeElement('div', 'photo-placeholder', 'No photo yet'))
  }

  const body = makeElement('div', 'pet-card-body')
  body.append(makeElement('span', `status status-${post.status.toLowerCase()}`, post.status))

  const title = post.pet_name || `${post.status === 'LOST' ? 'Lost' : 'Found'} ${post.species}`
  body.append(makeElement('h3', '', title))
  body.append(makeElement('p', 'pet-kind', [post.species, post.breed].filter(Boolean).join(' | ')))
  body.append(makeElement('p', 'pet-description', post.description))
  body.append(makeElement('p', 'pet-meta', `${post.area}, ${post.district} | ${displayDate(post.event_date)}`))

  const contact = [post.contact_name, post.contact_phone, post.contact_email].filter(Boolean).join(' | ')
  body.append(makeElement('p', 'pet-contact', `Contact: ${contact}`))
  card.append(body)
  return card
}

async function loadPets() {
  refreshButton.disabled = true
  messageElement.hidden = false
  messageElement.textContent = 'Loading pet posts...'

  try {
    const response = await fetch(`${apiBaseUrl}/pets`)
    if (!response.ok) throw new Error(`API returned ${response.status}`)

    const posts = await response.json()
    if (!Array.isArray(posts)) throw new Error('Unexpected API response')

    petsElement.replaceChildren(...posts.map(petCard))
    messageElement.textContent = posts.length ? '' : 'No pet posts yet.'
    messageElement.hidden = posts.length > 0
  } catch {
    petsElement.replaceChildren()
    messageElement.textContent = 'Could not load pet posts. Check that the API is running, then try again.'
  } finally {
    refreshButton.disabled = false
  }
}

async function loadOwnedReports() {
  const ids = ownedReportIds()
  ownedRefreshButton.disabled = true
  ownedMessageElement.hidden = false
  ownedMessageElement.textContent = 'Loading your reports...'

  try {
    const results = await Promise.allSettled(ids.map(async (id) => {
      const response = await fetch(`${apiBaseUrl}/pets/${id}`)
      if (response.status === 404) return null
      if (!response.ok) throw new Error(`API returned ${response.status}`)
      return response.json()
    }))
    const posts = results
      .filter((result) => result.status === 'fulfilled' && result.value)
      .map((result) => result.value)
      .sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id)
    const failed = results.some((result) => result.status === 'rejected')

    ownedPetsElement.replaceChildren(...posts.map(petCard))
    ownedMessageElement.textContent = failed
      ? 'Some reports could not be loaded. Try refreshing.'
      : posts.length ? '' : 'No reports saved in this browser are available.'
    ownedMessageElement.hidden = posts.length > 0 && !failed
  } catch {
    ownedPetsElement.replaceChildren()
    ownedMessageElement.textContent = 'Could not load your reports. Please try refreshing.'
  } finally {
    ownedRefreshButton.disabled = false
  }
}

function showBrowse() {
  closeCalendar()
  reportSection.hidden = true
  ownedSection.hidden = true
  browseSection.hidden = false
  updateOwnedAction()
  window.scrollTo({ top: 0 })
}

function showReport() {
  browseSection.hidden = true
  ownedSection.hidden = true
  reportSection.hidden = false
  reportHeading.focus()
  window.scrollTo({ top: 0 })
}

function showOwnedReports() {
  closeCalendar()
  browseSection.hidden = true
  reportSection.hidden = true
  ownedSection.hidden = false
  ownedHeading.focus()
  window.scrollTo({ top: 0 })
  loadOwnedReports()
}

function showFormError(message) {
  formError.textContent = message
  formError.hidden = false
}

function photoProblem(file) {
  if (!file) return null
  if (!allowedPhotoTypes.includes(file.type)) return 'Choose a JPEG, PNG or WEBP photo.'
  if (file.size > maxPhotoBytes) return 'Choose a photo smaller than 5 MB.'
  return null
}

async function apiErrorMessage(response) {
  const body = await response.json().catch(() => null)
  if (Array.isArray(body?.detail)) {
    return body.detail.map((error) => {
      const field = error.loc?.at(-1)
      const label = fieldNames[field] || field || 'Report'
      return `${label}: ${error.msg?.replace(/^Value error, /, '') || 'Invalid value'}`
    }).join('; ')
  }
  return typeof body?.detail === 'string' ? body.detail : `Server returned ${response.status}.`
}

function setResult(message, canRetry = false) {
  closeCalendar()
  reportForm.hidden = true
  resultPanel.hidden = false
  resultPanel.classList.toggle('has-warning', canRetry)
  resultMessage.textContent = message + (accessSaved ? '' : ' This browser could not save access to manage this report later.')
  retryPhotoButton.hidden = !canRetry
  retryPhotoField.hidden = !canRetry
}

async function uploadPhoto(id, token, file) {
  const upload = new FormData()
  upload.append('photo', file)
  const response = await fetch(`${apiBaseUrl}/pets/${id}/photo`, {
    method: 'POST',
    headers: { 'X-Edit-Token': token },
    body: upload,
  })
  if (!response.ok) throw new Error(await apiErrorMessage(response))
}

async function submitReport(event) {
  event.preventDefault()
  formError.hidden = true

  for (const name of requiredTextFields) {
    const field = reportForm.elements.namedItem(name)
    if (!field.value.trim()) {
      field.setCustomValidity('Please fill out this field.')
      field.reportValidity()
      return
    }
  }

  const eventDate = apiDate(dateFields.map((field) => field.value).join('/'))
  if (!eventDate) {
    dateFields[0].setCustomValidity('Enter a real date as dd/mm/yyyy.')
    dateFields[0].reportValidity()
    return
  }
  if (eventDate > todayIndiaIso()) {
    dateFields[2].setCustomValidity('Lost or found date cannot be in the future.')
    dateFields[2].reportValidity()
    return
  }

  const photo = reportForm.elements.namedItem('photo').files[0]
  const photoError = photoProblem(photo)
  if (photoError) {
    showFormError(photoError)
    return
  }

  const formData = new FormData(reportForm)
  const value = (name) => String(formData.get(name) || '').trim()
  const payload = {
    status: value('status'),
    species: value('species'),
    breed: value('breed') || null,
    pet_name: value('pet_name') || null,
    description: value('description'),
    area: value('area'),
    district: value('district'),
    event_date: eventDate,
    contact_name: value('contact_name'),
    contact_phone: value('contact_phone'),
    contact_email: value('contact_email') || null,
  }

  submitButton.disabled = true
  submitButton.textContent = 'Creating report...'
  backButton.disabled = true
  reportForm.setAttribute('aria-busy', 'true')

  try {
    let response
    try {
      response = await fetch(`${apiBaseUrl}/pets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    } catch {
      showFormError('Could not confirm whether the report was created. Check the list before trying again.')
      return
    }

    if (!response.ok) {
      const detail = await apiErrorMessage(response)
      showFormError(response.status === 422
        ? `Please check the report: ${detail}`
        : `Could not confirm whether the report was created. Check the list before trying again. ${detail}`)
      return
    }

    const created = await response.json().catch(() => null)
    if (!Number.isInteger(created?.id) || !created.edit_token) {
      showFormError('The report may have been created, but its confirmation was incomplete. Check the list before trying again.')
      return
    }

    // Save ownership before any optional photo request, even if that request fails.
    accessSaved = true
    try {
      localStorage.setItem(editTokenKey(created.id), created.edit_token)
    } catch {
      accessSaved = false
    }
    updateOwnedAction()

    setResult(photo ? 'Your report was created. Uploading its photo...' : 'Your report was created and is ready to browse.')
    if (photo) {
      try {
        await uploadPhoto(created.id, created.edit_token, photo)
        setResult('Your report and photo were added successfully.')
      } catch (error) {
        pendingPhoto = { id: created.id, token: created.edit_token, file: photo }
        setResult(`Your report was created, but the photo could not be uploaded. ${error.message} You can retry below without creating another report.`, true)
      }
    }
    await loadPets()
  } finally {
    submitButton.disabled = false
    submitButton.textContent = 'Create report'
    backButton.disabled = false
    reportForm.removeAttribute('aria-busy')
  }
}

async function retryPhoto() {
  if (!pendingPhoto) return
  const file = retryPhotoInput.files[0] || pendingPhoto.file
  const problem = photoProblem(file)
  if (problem) {
    setResult(`Your report is already created. ${problem} Choose another photo to retry.`, true)
    return
  }

  pendingPhoto.file = file
  retryPhotoButton.disabled = true
  retryPhotoButton.textContent = 'Uploading photo...'
  try {
    await uploadPhoto(pendingPhoto.id, pendingPhoto.token, file)
    pendingPhoto = null
    retryPhotoInput.value = ''
    setResult('Your report and photo were added successfully.')
    await loadPets()
  } catch (error) {
    setResult(`Your report is already created, but the photo still could not be uploaded. ${error.message} You can retry without creating another report.`, true)
  } finally {
    retryPhotoButton.disabled = false
    retryPhotoButton.textContent = 'Retry photo upload'
  }
}

function createAnotherReport() {
  closeCalendar()
  pendingPhoto = null
  accessSaved = true
  reportForm.reset()
  retryPhotoInput.value = ''
  reportForm.querySelectorAll('[required]').forEach((field) => field.setCustomValidity(''))
  formError.hidden = true
  formError.textContent = ''
  resultPanel.hidden = true
  resultPanel.classList.remove('has-warning')
  resultMessage.textContent = ''
  retryPhotoButton.hidden = true
  retryPhotoField.hidden = true
  reportForm.hidden = false
  showReport()
  reportForm.elements.namedItem('status').focus()
}

reportForm.querySelectorAll('[required]').forEach((field) => {
  field.addEventListener('input', () => field.setCustomValidity(''))
})
dateFields.forEach((field, index) => {
  field.addEventListener('input', () => {
    field.value = field.value.replace(/\D/g, '').slice(0, field.maxLength)
    dateFields.forEach((part) => part.setCustomValidity(''))
    const selected = selectedDate()
    if (!calendar.hidden && selected) {
      const [year, month] = selected.split('-').map(Number)
      shownMonth = new Date(year, month - 1, 1)
      renderCalendar()
      positionCalendar()
    }
    if (field.value.length === field.maxLength && index < dateFields.length - 1) dateFields[index + 1].focus()
  })
})
dateFields[0].addEventListener('paste', (event) => {
  const pasted = event.clipboardData.getData('text').trim()
  const match = /^(\d{2})\/?(\d{2})\/?(\d{4})$/.exec(pasted)
  if (!match) return
  event.preventDefault()
  dateFields.forEach((field, index) => {
    field.value = match[index + 1]
    field.setCustomValidity('')
  })
  dateFields[2].focus()
})
calendarButton.addEventListener('click', () => {
  if (!calendar.hidden) {
    closeCalendar()
    return
  }
  const selected = selectedDate()
  const initial = (selected && selected <= todayIndiaIso() ? selected : todayIndiaIso()).split('-').map(Number)
  shownMonth = new Date(initial[0], initial[1] - 1, 1)
  renderCalendar()
  calendar.hidden = false
  calendarButton.setAttribute('aria-expanded', 'true')
  positionCalendar()
})
document.querySelector('#calendar-previous').addEventListener('click', () => {
  shownMonth = new Date(shownMonth.getFullYear(), shownMonth.getMonth() - 1, 1)
  renderCalendar()
  positionCalendar()
})
document.querySelector('#calendar-next').addEventListener('click', () => {
  shownMonth = new Date(shownMonth.getFullYear(), shownMonth.getMonth() + 1, 1)
  renderCalendar()
  positionCalendar()
})
calendarDays.addEventListener('click', (event) => {
  const day = event.target.closest('button[data-date]')
  if (!day) return
  setDateFields(day.dataset.date)
  closeCalendar()
  calendarButton.focus()
})
document.querySelector('#calendar-today').addEventListener('click', () => {
  setDateFields(todayIndiaIso())
  closeCalendar()
  calendarButton.focus()
})
document.querySelector('#calendar-clear').addEventListener('click', () => {
  setDateFields('')
  closeCalendar()
  dateFields[0].focus()
})
document.addEventListener('click', (event) => {
  if (!calendar.hidden && !calendar.contains(event.target) && !calendarButton.contains(event.target)) closeCalendar()
})
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !calendar.hidden) {
    closeCalendar()
    calendarButton.focus()
  }
})
window.addEventListener('resize', positionCalendar)
window.addEventListener('scroll', positionCalendar, { passive: true })
refreshButton.addEventListener('click', loadPets)
ownedRefreshButton.addEventListener('click', loadOwnedReports)
viewOwnedButton.addEventListener('click', showOwnedReports)
document.querySelector('#owned-browse-button').addEventListener('click', showBrowse)
document.querySelector('#owned-create-button').addEventListener('click', createAnotherReport)
newReportButton.addEventListener('click', createAnotherReport)
backButton.addEventListener('click', showBrowse)
document.querySelector('#browse-after-submit-button').addEventListener('click', showBrowse)
document.querySelector('#view-owned-after-submit-button').addEventListener('click', showOwnedReports)
document.querySelector('#create-another-button').addEventListener('click', createAnotherReport)
reportForm.addEventListener('submit', submitReport)
retryPhotoButton.addEventListener('click', retryPhoto)
updateOwnedAction()
loadPets()
