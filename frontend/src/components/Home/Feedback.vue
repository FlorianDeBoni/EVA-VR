<template>
  <div class="feedback" ref="rootRef">
    <span class="feedback__label">Helpful?</span>

    <button
      class="feedback__btn"
      :class="{ 'feedback__btn--active feedback__btn--up': pendingFeedback === 'up' }"
      @click="selectFeedback('up')"
      aria-label="Thumbs up"
    >
      <svg class="thumb-icon" width="18" height="18" viewBox="0 0 27 27" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" clip-rule="evenodd" d="M0.7229 26.5H5.92292V10.9008H0.7229V26.5ZM26.6299 15.2618L24.372 23.7566C23.9989 25.3696 22.5621 26.5 20.9072 26.5H8.52293V10.9278L10.7573 2.87293C10.9669 1.50799 12.1418 0.5 13.524 0.5C15.0699 0.5 16.323 1.7527 16.323 3.29837V10.8998H23.1651C25.4519 10.9009 27.1453 13.0335 26.6299 15.2618Z"/>
      </svg>
    </button>

    <button
      class="feedback__btn"
      :class="{ 'feedback__btn--active feedback__btn--down': pendingFeedback === 'down' }"
      @click="selectFeedback('down')"
      aria-label="Thumbs down"
    >
      <svg class="thumb-icon" width="18" height="18" viewBox="0 0 27 27" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" clip-rule="evenodd" d="M26.7229 0.5L21.5229 0.5L21.5229 16.0992L26.7229 16.0992L26.7229 0.5ZM0.815853 11.7382L3.07376 3.24339C3.44687 1.63037 4.88372 0.500027 6.53861 0.500027L18.9229 0.500028L18.9229 16.0722L16.6885 24.1271C16.4789 25.492 15.304 26.5 13.9218 26.5C12.3759 26.5 11.1228 25.2473 11.1228 23.7016L11.1228 16.1002L4.28068 16.1002C1.99391 16.0991 0.300502 13.9664 0.815853 11.7382Z"/>
      </svg>
    </button>

    <transition :name="popoverPlacement === 'top' ? 'pop-top' : 'pop-bottom'">
      <div
        v-if="pendingFeedback"
        class="feedback__popover"
        :class="`feedback__popover--${popoverPlacement}`"
        ref="popoverRef"
      >
        <!-- Arrow indicator -->
        <div class="feedback__popover-arrow" />

        <div class="feedback__popover-header">
          <span class="feedback__popover-title">
            {{ pendingFeedback === 'up' ? '👍 Glad it helped!' : '👎 Sorry to hear that.' }}
          </span>
          <span v-if="submittedCount > 0" class="feedback__submitted-badge">
            {{ submittedCount }} sent
          </span>
        </div>
        <textarea
          v-model="feedbackNote"
          class="feedback__textarea"
          placeholder="Any additional comments? (optional)"
          rows="3"
          autofocus
        />
        <div class="feedback__popover-actions">
          <button class="feedback__cancel" @click="cancelFeedback">Cancel</button>
          <button class="feedback__submit" @click="submitFeedback">Send feedback</button>
        </div>
      </div>
    </transition>

    <transition name="fade">
      <span v-if="justSubmitted" class="feedback__thanks">✓ Thanks!</span>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const emit = defineEmits<{
  (e: 'feedback', payload: { rating: 'up' | 'down'; note: string }): void
}>()

const POPOVER_HEIGHT = 180   // approximate rendered height in px
const MARGIN        = 8      // gap between trigger and popover

const pendingFeedback  = ref<'up' | 'down' | null>(null)
const feedbackNote     = ref('')
const submittedCount   = ref(0)
const justSubmitted    = ref(false)
const rootRef          = ref<HTMLElement | null>(null)
const popoverRef       = ref<HTMLElement | null>(null)
const popoverPlacement = ref<'bottom' | 'top'>('bottom')

/** Re-measure whenever the popover is about to open */
function measurePlacement() {
  if (!rootRef.value) return
  const rect       = rootRef.value.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom
  const spaceAbove = rect.top

  // Prefer below; flip to above only if below is too tight AND above has more room
  popoverPlacement.value =
    spaceBelow < POPOVER_HEIGHT + MARGIN && spaceAbove > spaceBelow
      ? 'top'
      : 'bottom'
}

watch(pendingFeedback, async (val) => {
  if (val) {
    measurePlacement()
    // Also re-check once the popover is rendered (actual height may differ)
    await nextTick()
    if (popoverRef.value && rootRef.value) {
      const actualHeight = popoverRef.value.offsetHeight
      const rect         = rootRef.value.getBoundingClientRect()
      const spaceBelow   = window.innerHeight - rect.bottom
      const spaceAbove   = rect.top
      if (spaceBelow < actualHeight + MARGIN && spaceAbove > spaceBelow) {
        popoverPlacement.value = 'top'
      } else {
        popoverPlacement.value = 'bottom'
      }
    }
  }
})

function selectFeedback(rating: 'up' | 'down') {
  pendingFeedback.value = pendingFeedback.value === rating ? null : rating
  feedbackNote.value = ''
}

function cancelFeedback() {
  pendingFeedback.value = null
  feedbackNote.value = ''
}

function submitFeedback() {
  if (!pendingFeedback.value) return
  emit('feedback', { rating: pendingFeedback.value, note: feedbackNote.value })
  submittedCount.value++
  pendingFeedback.value = null
  feedbackNote.value = ''
  justSubmitted.value = true
  setTimeout(() => { justSubmitted.value = false }, 2000)
}
</script>

<style scoped>
/* ── Wrapper ── */
.feedback {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  width: fit-content;
}

.feedback__label {
  font-size: 11px;
  color: #9ca3af;
  margin-right: 4px;
  user-select: none;
  letter-spacing: 0.01em;
}

/* ── Buttons ── */
.feedback__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: none;
  border: 1.5px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  padding: 6px;
  color: #d1d5db;
  transition: color 0.2s ease-in-out, border-color 0.2s ease-in-out, background 0.2s ease-in-out;
}

.feedback__btn:hover {
  color: #6b7280;
  border-color: #e5e7eb;
  background: #f9fafb;
}

.feedback__btn:hover .thumb-icon { transform: scale(1.25); }

.thumb-icon {
  transition: transform 0.2s ease-in-out;
  display: block;
}

.feedback__btn--up.feedback__btn--active  { color: #1877f2; border-color: #bfdbfe; background: #eff6ff; }
.feedback__btn--down.feedback__btn--active { color: #ef4444; border-color: #fecaca; background: #fef2f2; }

.feedback__btn--active .thumb-icon {
  animation: keyframes-fill 0.2s ease-in-out;
}

@keyframes keyframes-fill {
  0%   { transform: scale(0); opacity: 0; }
  50%  { transform: scale(1.3) rotate(-10deg); }
  100% { transform: scale(1); opacity: 1; }
}

/* ── Popover ── */
.feedback__popover {
  position: absolute;
  right: 0;
  width: 256px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.12);
  padding: 14px;
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Placement: below the trigger */
.feedback__popover--bottom {
  top: calc(100% + 8px);
}

/* Placement: above the trigger */
.feedback__popover--top {
  bottom: calc(100% + 8px);
}

/* ── Arrow ── */
.feedback__popover-arrow {
  position: absolute;
  right: 22px;       /* aligns roughly under the thumb buttons */
  width: 10px;
  height: 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  transform: rotate(45deg);
  /* hide the part of the border that overlaps the popover body */
}

.feedback__popover--bottom .feedback__popover-arrow {
  top: -6px;
  border-bottom-color: transparent;
  border-right-color: transparent;
}

.feedback__popover--top .feedback__popover-arrow {
  bottom: -6px;
  border-top-color: transparent;
  border-left-color: transparent;
}

/* ── Popover internals ── */
.feedback__popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.feedback__popover-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.feedback__submitted-badge {
  font-size: 11px;
  background: #ecfdf5;
  color: #10b981;
  border-radius: 20px;
  padding: 2px 8px;
  font-weight: 500;
}

.feedback__textarea {
  width: 100%;
  resize: none;
  border: 1.5px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  color: #374151;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.15s ease;
  box-sizing: border-box;
  background: #fafafa;
}

.feedback__textarea:focus        { border-color: #93c5fd; background: #fff; }
.feedback__textarea::placeholder { color: #d1d5db; }

.feedback__popover-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.feedback__cancel,
.feedback__submit {
  padding: 6px 14px;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background 0.15s ease, transform 0.1s ease;
}

.feedback__cancel        { background: #f3f4f6; color: #6b7280; }
.feedback__cancel:hover  { background: #e5e7eb; }
.feedback__submit        { background: #3b82f6; color: #fff; }
.feedback__submit:hover  { background: #2563eb; }
.feedback__submit:active { transform: scale(0.97); }

/* ── Thanks flash ── */
.feedback__thanks {
  font-size: 11px;
  color: #10b981;
  font-weight: 500;
  margin-left: 4px;
}

/* ── Transitions ── */

/* Popover opening downward */
.pop-bottom-enter-active {
  animation: popoverInBottom 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.pop-bottom-leave-active {
  animation: popoverInBottom 0.12s ease-in reverse;
}

@keyframes popoverInBottom {
  from { opacity: 0; transform: scale(0.92) translateY(-6px); }
  to   { opacity: 1; transform: scale(1)    translateY(0);    }
}

/* Popover opening upward */
.pop-top-enter-active {
  animation: popoverInTop 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.pop-top-leave-active {
  animation: popoverInTop 0.12s ease-in reverse;
}

@keyframes popoverInTop {
  from { opacity: 0; transform: scale(0.92) translateY(6px); }
  to   { opacity: 1; transform: scale(1)    translateY(0);   }
}

/* Thanks fade */
.fade-enter-active { transition: opacity 0.2s ease; }
.fade-leave-active { transition: opacity 0.4s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>