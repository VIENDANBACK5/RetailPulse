/**
 * LIVE LOCAL CLOCK
 * Updates every 1s displaying current user date and time
 */
const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

export function initClock(timeElemId = 'live-time-str', dateElemId = 'live-date-str') {
  const timeElem = document.getElementById(timeElemId);
  const dateElem = document.getElementById(dateElemId);

  function update() {
    const now = new Date();
    const hours = now.getHours();
    const mins = now.getMinutes();
    const meridiem = hours >= 12 ? 'pm' : 'am';
    const formattedHours = hours % 12 || 12;
    const formattedMins = String(mins).padStart(2, '0');
    const timeStr = `${formattedHours}:${formattedMins}${meridiem}`;

    const day = now.getDate();
    const month = monthNames[now.getMonth()];
    const year = now.getFullYear();
    const dateStr = `${day} ${month}, ${year}`;

    if (timeElem) timeElem.textContent = timeStr;
    if (dateElem) dateElem.textContent = dateStr;
  }

  update();
  setInterval(update, 1000);
}
