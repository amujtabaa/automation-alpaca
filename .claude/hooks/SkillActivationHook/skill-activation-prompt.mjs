#!/usr/bin/env node
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

async function main() {
    try {
        // Read input from stdin
        const input = readFileSync(0, 'utf-8');
        const data = JSON.parse(input);
        const prompt = (data.prompt || '').toLowerCase();
        if (!prompt) return;
        const sessionId = data.session_id;

        // Load skill and agent rules - derive project directory from script location
        // This file is in .claude/hooks/SkillActivationHook/, so project root is 3 levels up
        const __filename = fileURLToPath(import.meta.url);
        const __dirname = dirname(__filename);
        const projectDir = join(__dirname, '..', '..', '..');

        const skillRulesPath = join(projectDir, '.claude', 'skills', 'skill-rules.json');
        const agentRulesPath = join(projectDir, '.claude', 'agents', 'agent-rules.json');

        const skillRules = JSON.parse(readFileSync(skillRulesPath, 'utf-8'));

        let agentRules = { agents: {} };
        if (existsSync(agentRulesPath)) {
            agentRules = JSON.parse(readFileSync(agentRulesPath, 'utf-8'));
        }

        // State file for tracking recommendations per session
        const stateFilePath = join(__dirname, 'recommendation-log.json');

        // Load existing state
        let state = {};
        if (existsSync(stateFilePath)) {
            try {
                state = JSON.parse(readFileSync(stateFilePath, 'utf-8'));
            } catch (err) {
                // If state file is corrupted, start fresh
                state = {};
            }
        }

        // Cleanup old sessions (older than 7 days)
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
        const sevenDaysAgoISO = sevenDaysAgo.toISOString();

        for (const [sid, sessionData] of Object.entries(state)) {
            if (sessionData.lastUpdated && sessionData.lastUpdated < sevenDaysAgoISO) {
                delete state[sid];
            }
        }

        // Get already recommended skills and agents for this session
        const alreadyRecommendedSkills = state[sessionId]?.skills || [];
        const alreadyRecommendedAgents = state[sessionId]?.agents || [];
        const now = new Date();
        const lastUpdated = now.toISOString();
        const lastUpdatedDate = now.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        }).replace(',', '');

        const matchedSkills = [];
        const matchedAgents = [];

        // Check each skill for matches
        for (const [skillName, config] of Object.entries(skillRules.skills)) {
            const triggers = config.promptTriggers;
            if (!triggers) {
                continue;
            }

            // Skip if already recommended in this session
            if (alreadyRecommendedSkills.includes(skillName)) {
                continue;
            }

            // Keyword matching
            if (triggers.keywords) {
                const keywordMatch = triggers.keywords.some(kw =>
                    prompt.includes(kw.toLowerCase())
                );
                if (keywordMatch) {
                    matchedSkills.push({ name: skillName, matchType: 'keyword', config });
                    continue;
                }
            }

            // Intent pattern matching
            if (triggers.intentPatterns) {
                const intentMatch = triggers.intentPatterns.some(pattern => {
                    const regex = new RegExp(pattern, 'i');
                    return regex.test(prompt);
                });
                if (intentMatch) {
                    matchedSkills.push({ name: skillName, matchType: 'intent', config });
                }
            }
        }

        // Check each agent for matches
        for (const [agentName, config] of Object.entries(agentRules.agents)) {
            const triggers = config.promptTriggers;
            if (!triggers) {
                continue;
            }

            // Skip if already recommended in this session
            if (alreadyRecommendedAgents.includes(agentName)) {
                continue;
            }

            // Keyword matching
            if (triggers.keywords) {
                const keywordMatch = triggers.keywords.some(kw =>
                    prompt.includes(kw.toLowerCase())
                );
                if (keywordMatch) {
                    matchedAgents.push({ name: agentName, matchType: 'keyword', config });
                    continue;
                }
            }

            // Intent pattern matching
            if (triggers.intentPatterns) {
                const intentMatch = triggers.intentPatterns.some(pattern => {
                    const regex = new RegExp(pattern, 'i');
                    return regex.test(prompt);
                });
                if (intentMatch) {
                    matchedAgents.push({ name: agentName, matchType: 'intent', config });
                }
            }
        }

        // Generate output if NEW matches found
        if (matchedSkills.length > 0 || matchedAgents.length > 0) {
            let output = '';

            // Output skills first
            if (matchedSkills.length > 0) {
                output += '🎯 SKILL ACTIVATION CHECK\n\n';

                // Group by priority
                const criticalSkills = matchedSkills.filter(s => s.config.priority === 'critical');
                const highSkills = matchedSkills.filter(s => s.config.priority === 'high');
                const mediumSkills = matchedSkills.filter(s => s.config.priority === 'medium');
                const lowSkills = matchedSkills.filter(s => s.config.priority === 'low');

                if (criticalSkills.length > 0) {
                    output += '⚠️ CRITICAL SKILLS TO LOAD — You must load these skills now:\n';
                    criticalSkills.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                if (highSkills.length > 0) {
                    output += '📚 RECOMMENDED SKILLS TO LOAD — You must load these skills now:\n';
                    highSkills.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                if (mediumSkills.length > 0) {
                    output += '💡 SUGGESTED SKILLS TO LOAD — Load if directly relevant:\n';
                    mediumSkills.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                if (lowSkills.length > 0) {
                    output += '📌 OPTIONAL SKILLS TO LOAD:\n';
                    lowSkills.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                output += 'ACTION: Load skills before responding to gather context and reduce errors\n';
            }

            // Output agents below skills
            if (matchedAgents.length > 0) {
                if (matchedSkills.length > 0) {
                    output += '\n';
                }
                output += '🤖 AGENT ACTIVATION CHECK\n\n';

                // Group by priority
                const criticalAgents = matchedAgents.filter(a => a.config.priority === 'critical');
                const highAgents = matchedAgents.filter(a => a.config.priority === 'high');
                const mediumAgents = matchedAgents.filter(a => a.config.priority === 'medium');
                const lowAgents = matchedAgents.filter(a => a.config.priority === 'low');

                if (criticalAgents.length > 0) {
                    output += '⚠️ CRITICAL AGENTS TO DISPATCH:\n';
                    criticalAgents.forEach(a => output += `  → ${a.name}\n`);
                    output += '\n';
                }

                if (highAgents.length > 0) {
                    output += '📚 RECOMMENDED AGENTS TO DISPATCH:\n';
                    highAgents.forEach(a => output += `  → ${a.name}\n`);
                    output += '\n';
                }

                if (mediumAgents.length > 0) {
                    output += '💡 SUGGESTED AGENTS TO DISPATCH:\n';
                    mediumAgents.forEach(a => output += `  → ${a.name}\n`);
                    output += '\n';
                }

                if (lowAgents.length > 0) {
                    output += '📌 OPTIONAL AGENTS TO DISPATCH:\n';
                    lowAgents.forEach(a => output += `  → ${a.name}\n`);
                    output += '\n';
                }

                output += 'ACTION: Consider delegating to these agents to preserve main thread context\n';
            }

            console.log(output);

            // Update state with newly recommended skills and agents
            const newlyRecommendedSkills = matchedSkills.map(s => s.name);
            const newlyRecommendedAgents = matchedAgents.map(a => a.name);
            state[sessionId] = {
                skills: [...alreadyRecommendedSkills, ...newlyRecommendedSkills],
                agents: [...alreadyRecommendedAgents, ...newlyRecommendedAgents],
                lastUpdated,
                lastUpdatedDate
            };

            // Write updated state
            writeFileSync(stateFilePath, JSON.stringify(state, null, 2), 'utf-8');
        }

        process.exit(0);
    } catch (err) {
        console.error('Error in skill-activation-prompt hook:', err);
        process.exit(1);
    }
}

main().catch(err => {
    console.error('Uncaught error:', err);
    process.exit(1);
});
