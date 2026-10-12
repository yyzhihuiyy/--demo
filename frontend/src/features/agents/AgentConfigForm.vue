<script setup lang="ts">
import BaseButton from '../../shared/components/BaseButton.vue'
import FormField from '../../shared/components/FormField.vue'
import type { AgentConfig } from '../../shared/contracts'

const props = defineProps<{ config: AgentConfig; disabled?: boolean }>()

function addCard() {
  if (props.disabled) return
  if (!props.config.knowledge_cards) props.config.knowledge_cards = []
  props.config.knowledge_cards.push({ title: '', content: '' })
}

function removeCard(index: number) {
  if (props.disabled) return
  props.config.knowledge_cards?.splice(index, 1)
}
</script>

<template>
  <div class="agent-stack">
    <FormField label="智能体名称" for-id="agent-name" hint="例如：助农客服小助手">
      <input id="agent-name" v-model="config.name" :disabled="disabled" maxlength="200" placeholder="给你的客服智能体起个名字" />
    </FormField>
    <FormField label="职责" for-id="agent-duties" hint="它需要回答哪类问题、完成什么任务">
      <textarea id="agent-duties" v-model="config.duties" :disabled="disabled" placeholder="解答农产品咨询，说明价格与发货安排……" />
    </FormField>
    <FormField label="服务边界" for-id="agent-boundaries" hint="写清楚不做什么、不承诺什么（如退款结果、功效）">
      <textarea id="agent-boundaries" v-model="config.boundaries" :disabled="disabled" placeholder="只讨论本场商品；不做功效承诺；退款按平台政策登记……" />
    </FormField>
    <FormField label="行为指令" for-id="agent-instructions" hint="语气、顺序、遇到争议时的处理方式">
      <textarea id="agent-instructions" v-model="config.instructions" :disabled="disabled" placeholder="先确认问题再回答；遇到投诉先安抚再给处理路径……" />
    </FormField>
    <div class="form-field">
      <label>知识卡（参考资料，不会覆盖平台规则与服务边界）</label>
      <div v-if="!config.knowledge_cards?.length" class="text-muted small">还没有知识卡，点击下方按钮添加第一张。</div>
      <div v-for="(card, index) in config.knowledge_cards ?? []" :key="index" class="agent-card">
        <input v-model="card.title" :disabled="disabled" maxlength="100" placeholder="知识卡标题（如：商品知识卡）" />
        <textarea v-model="card.content" :disabled="disabled" placeholder="知识卡内容：价格、发货时效、售后政策等依据" />
        <button v-if="!disabled" type="button" class="text-button" @click="removeCard(index)">删除该知识卡</button>
      </div>
      <BaseButton v-if="!disabled" variant="secondary" type="button" @click="addCard">＋ 添加知识卡</BaseButton>
    </div>
  </div>
</template>
