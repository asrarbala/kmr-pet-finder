import './style.css'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const petsElement = document.querySelector('#pets')
const messageElement = document.querySelector('#message')
const refreshButton = document.querySelector('#refresh-button')

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
  body.append(makeElement('p', 'pet-kind', [post.species, post.breed].filter(Boolean).join(' · ')))
  body.append(makeElement('p', 'pet-description', post.description))
  body.append(makeElement('p', 'pet-meta', `${post.area}, ${post.district} · ${post.event_date}`))

  const contact = [post.contact_name, post.contact_phone, post.contact_email].filter(Boolean).join(' · ')
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

refreshButton.addEventListener('click', loadPets)
loadPets()
