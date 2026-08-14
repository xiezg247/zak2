<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const props = withDefaults(
  defineProps<{
    source: string
  }>(),
  {
    source: '',
  },
)

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false,
})

const rendered = computed(() => md.render(props.source || ''))
</script>

<template>
  <div class="markdown" v-html="rendered"></div>
</template>

<style scoped>
.markdown {
  color: var(--ink);
  font-size: 0.9rem;
  line-height: 1.75;
  word-break: break-word;
}
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4) {
  margin: 1.5em 0 0.6em;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: -0.01em;
}
.markdown :deep(h1) {
  font-size: 1.4rem;
  padding-bottom: 0.4em;
  border-bottom: 1px solid var(--line-soft);
}
.markdown :deep(h2) {
  font-size: 1.2rem;
  padding-bottom: 0.35em;
  border-bottom: 1px solid var(--line-soft);
}
.markdown :deep(h3) {
  font-size: 1.05rem;
}
.markdown :deep(h4) {
  font-size: 0.95rem;
}
.markdown :deep(h1:first-child),
.markdown :deep(h2:first-child),
.markdown :deep(h3:first-child),
.markdown :deep(h4:first-child) {
  margin-top: 0;
}
.markdown :deep(p) {
  margin: 0.7em 0;
}
.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 0.7em 0;
  padding-left: 1.5em;
}
.markdown :deep(li) {
  margin: 0.3em 0;
}
.markdown :deep(li > ul),
.markdown :deep(li > ol) {
  margin: 0.2em 0;
}
.markdown :deep(blockquote) {
  margin: 0.9em 0;
  padding: 0.4em 1em;
  border-left: 3px solid var(--brand-soft);
  background: var(--brand-light);
  border-radius: 0 0.5rem 0.5rem 0;
  color: var(--ink-muted);
}
.markdown :deep(blockquote p) {
  margin: 0.3em 0;
}
.markdown :deep(a) {
  color: var(--brand);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.markdown :deep(a:hover) {
  color: var(--brand-dark);
}
.markdown :deep(code) {
  font-family: var(--mono);
  font-size: 0.85em;
  background: var(--surface-muted);
  border: 1px solid var(--line-soft);
  border-radius: 0.375rem;
  padding: 0.1em 0.4em;
  color: var(--brand-dark);
}
.markdown :deep(pre) {
  margin: 0.9em 0;
  padding: 12px 14px;
  background: var(--surface-muted);
  border: 1px solid var(--line);
  border-radius: 0.625rem;
  overflow-x: auto;
}
.markdown :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
  color: var(--ink);
  font-size: 0.82rem;
  line-height: 1.6;
}
.markdown :deep(table) {
  border-collapse: collapse;
  margin: 0.9em 0;
  display: block;
  overflow-x: auto;
  max-width: 100%;
}
.markdown :deep(th),
.markdown :deep(td) {
  border: 1px solid var(--line);
  padding: 0.5rem 0.75rem;
  text-align: left;
  font-size: 0.85rem;
}
.markdown :deep(th) {
  background: var(--surface-muted);
  font-weight: 600;
}
.markdown :deep(hr) {
  border: none;
  border-top: 1px solid var(--line);
  margin: 1.5em 0;
}
.markdown :deep(strong) {
  font-weight: 600;
}
.markdown :deep(img) {
  max-width: 100%;
  border-radius: 0.5rem;
}
</style>
