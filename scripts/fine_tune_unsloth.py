"""
AML Transaction Intelligence - Unsloth Fine-tuning Script
==========================================================
Fine-tune Llama-3 for AML case explanation using LoRA + Unsloth
for 2x faster training and 70% less memory.

Usage:
    python scripts/fine_tune_unsloth.py --max_steps 100
    python scripts/fine_tune_unsloth.py --epochs 1 --output_dir ./models/aml-expert
"""

import os
import json
import argparse
from datetime import datetime

# Check for GPU availability first
try:
    import torch
    if not torch.cuda.is_available():
        print("WARNING: CUDA not available. Training will be slow or may fail.")
        print("Consider using Google Colab with GPU runtime for training.")
    else:
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
except ImportError:
    print("PyTorch not installed. Please install torch first.")

# Unsloth imports
try:
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template
    UNSLOTH_AVAILABLE = True
except ImportError:
    print("Unsloth not installed. Install with:")
    print("pip install 'unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git'")
    UNSLOTH_AVAILABLE = False

from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# ============================================================================
# AML INSTRUCTION DATASET (Small, High-Quality)
# ============================================================================
# This is a curated dataset of AML reasoning examples.
# The model learns the *logic* of AML regulation, not just pattern matching.

AML_TRAINING_DATA = [
    {
        "instruction": "Analyze this transaction pattern for potential money laundering.",
        "input": "Account 8001A sent 5 transactions totaling $52,000 within 10 minutes to 3 different accounts.",
        "output": """## Risk Assessment: HIGH

**Pattern Identified:** Rapid fund dispersion (Fan-Out)

**FATF Red Flags Triggered:**
1. **Structuring/Smurfing**: Multiple rapid transactions suggest intentional splitting to avoid reporting thresholds ($10,000 CTR limit).
2. **Layering Behavior**: Dispersing funds to multiple accounts within minutes is a classic layering technique.
3. **Velocity Anomaly**: 5 transactions in 10 minutes is statistically abnormal for legitimate business.

**Recommended Actions:**
- File SAR (Suspicious Activity Report) within 30 days
- Freeze account pending investigation
- Request source of funds documentation
- Check beneficiary accounts for shell company indicators"""
    },
    {
        "instruction": "Evaluate this alert for AML compliance concerns.",
        "input": "A retail customer made 12 cash deposits of $9,500 each over 3 days at different branches.",
        "output": """## Risk Assessment: CRITICAL

**Pattern Identified:** Structured deposits (Smurfing)

**FATF Red Flags Triggered:**
1. **Deliberate Threshold Avoidance**: Each deposit is just below the $10,000 CTR threshold - classic structuring.
2. **Geographic Distribution**: Using multiple branches indicates awareness of detection systems.
3. **High Volume**: $114,000 in 3 days is inconsistent with typical retail customer behavior.

**Regulatory Violations:**
- 31 U.S.C. § 5324: Structuring transactions to evade reporting requirements
- This is a federal crime regardless of the source of funds

**Recommended Actions:**
- Immediate SAR filing (within 24 hours due to severity)
- Enhanced due diligence on customer's business activities
- Review historical transaction patterns for similar behavior"""
    },
    {
        "instruction": "Assess the money laundering risk of this wire transfer.",
        "input": "A newly opened business account received $2.3M wire from a jurisdiction with weak AML controls, then immediately sent 80% to 5 different countries.",
        "output": """## Risk Assessment: CRITICAL

**Pattern Identified:** Pass-through account with high-risk jurisdiction

**FATF Red Flags Triggered:**
1. **High-Risk Jurisdiction**: Wire origin from FATF grey-listed country requires enhanced scrutiny.
2. **New Account + High Value**: Large transfers through newly opened accounts are inherently suspicious.
3. **Immediate Dispersion**: Moving 80% of funds within 24 hours indicates transit/layering behavior.
4. **Multi-Jurisdictional Layering**: Splitting to 5 countries makes fund tracing extremely difficult.

**Potential Typologies:**
- Trade-based money laundering
- Correspondent banking abuse
- Shell company network

**Recommended Actions:**
- Immediate transaction hold pending review
- Request full KYB (Know Your Business) documentation
- Verify beneficial ownership through independent sources
- Consider law enforcement referral"""
    },
    {
        "instruction": "Determine if this transaction pattern indicates money laundering.",
        "input": "Customer receives regular $4,000 deposits every Monday for 6 months, consistent with payroll timing.",
        "output": """## Risk Assessment: LOW

**Pattern Identified:** Regular payroll deposits

**Analysis:**
1. **Consistency**: Regular timing and amounts align with legitimate employment income.
2. **Below Threshold**: Amounts are well below structuring concerns.
3. **Predictable Pattern**: 6-month history establishes normal behavior baseline.

**FATF Red Flags:** None identified

**Conclusion:**
This pattern is consistent with legitimate payroll activity. No suspicious indicators present.

**Recommended Actions:**
- No action required
- Continue standard monitoring
- Document in customer profile as established baseline"""
    },
    {
        "instruction": "Analyze this cross-border transaction for AML red flags.",
        "input": "Import company receives invoice payment of $890,000 from a supplier, but the goods value on customs declaration shows only $120,000.",
        "output": """## Risk Assessment: CRITICAL

**Pattern Identified:** Trade-Based Money Laundering (TBML) - Over-invoicing

**FATF Red Flags Triggered:**
1. **Price Discrepancy**: 7.4x difference between payment and declared goods value is a major red flag.
2. **Value Transfer Mechanism**: Over-invoicing allows illicit funds to appear as legitimate trade payments.
3. **Documentary Fraud**: Customs declaration inconsistency suggests falsified trade documents.

**TBML Indicators:**
- Payments significantly exceed fair market value
- Inconsistent documentation between banking and customs records
- Potential circular trading arrangement

**Regulatory Concerns:**
- FATF Recommendation 20: Suspicious Transaction Reporting
- FATF Recommendation 32: Cash Couriers (if related to trade finance fraud)

**Recommended Actions:**
- Request original invoices, bills of lading, and customs documents
- Verify goods shipment through independent logistics records
- Cross-reference with supplier's banking jurisdiction
- File SAR with detailed TBML analysis"""
    },
    {
        "instruction": "Evaluate this cryptocurrency-related transaction for money laundering risk.",
        "input": "Customer deposited $50,000 cash, immediately purchased Bitcoin, transferred to external wallet, then received $48,000 wire from an unrelated foreign entity.",
        "output": """## Risk Assessment: HIGH

**Pattern Identified:** Cryptocurrency layering with fiat conversion

**FATF Red Flags Triggered:**
1. **Cash-to-Crypto Conversion**: Large cash deposits immediately converted to cryptocurrency bypass traditional banking controls.
2. **External Wallet Transfer**: Moving crypto to external custody eliminates transaction traceability.
3. **Circular Value Transfer**: Receiving nearly equivalent value from unrelated foreign entity suggests roundtrip laundering.

**Virtual Asset Red Flags (FATF Guidance):**
- Immediate conversion of large cash deposits to virtual assets
- Transfer to unhosted/external wallets
- Receipt of funds from parties with no apparent business relationship

**Enhanced Due Diligence Required:**
- Source of $50,000 cash
- Purpose of cryptocurrency transaction
- Relationship with foreign wire sender
- Blockchain analysis of wallet addresses

**Recommended Actions:**
- Request detailed explanation of transaction purpose
- Conduct blockchain forensics on destination wallet
- Verify foreign entity through independent sources
- Consider filing SAR for cryptocurrency-related suspicious activity"""
    },
    {
        "instruction": "Assess this PEP-related transaction for compliance risk.",
        "input": "Account linked to a foreign government official received $500,000 labeled as 'consulting fees' from a company that recently won a government contract.",
        "output": """## Risk Assessment: CRITICAL

**Pattern Identified:** Potential PEP corruption/bribery

**FATF Red Flags Triggered:**
1. **PEP Association**: Account linked to Politically Exposed Person requires enhanced due diligence.
2. **Suspicious Labeling**: Generic 'consulting fees' description lacks specificity.
3. **Government Contract Nexus**: Payment timing correlates with contract award - classic corruption indicator.
4. **Value Inconsistency**: Consulting fees should be proportionate to documented services.

**FCPA/Anti-Bribery Concerns:**
- Potential violation of Foreign Corrupt Practices Act
- UK Bribery Act implications if UK nexus exists
- Local anti-corruption law violations

**FATF Recommendations Applicable:**
- Recommendation 12: Politically Exposed Persons
- Recommendation 20: Reporting of Suspicious Transactions

**Recommended Actions:**
- Immediate enhanced due diligence
- Request consulting contract and deliverables documentation
- Verify services rendered through independent sources
- File SAR with corruption/bribery indicators
- Consider regulatory notification requirements"""
    },
    {
        "instruction": "Analyze this unusual account activity pattern.",
        "input": "Dormant personal account suddenly receives 47 small transfers ($200-$500) from different senders within 24 hours totaling $18,000.",
        "output": """## Risk Assessment: HIGH

**Pattern Identified:** Money mule / Fund aggregation

**FATF Red Flags Triggered:**
1. **Dormancy Breach**: Sudden activity after period of inactivity is suspicious.
2. **Multiple Small Transfers**: Many small amounts from different sources indicate aggregation.
3. **Volume Anomaly**: 47 transfers in 24 hours is statistically abnormal.

**Potential Typologies:**
- Money mule account (willing or unwitting)
- Romance scam collection point
- Cryptocurrency exchange aggregation
- Payroll fraud collection

**Risk Indicators:**
- Account holder may be victim of account takeover
- Account holder may be recruited as money mule
- Senders may be fraud victims

**Recommended Actions:**
- Contact account holder to verify legitimacy
- Freeze account pending verification
- Review sender accounts for fraud patterns
- Coordinate with fraud department
- File SAR if suspicious activity confirmed"""
    },
]

# ============================================================================
# FINE-TUNING CONFIGURATION
# ============================================================================

def get_model_config(model_size: str = "8b"):
    """Get model configuration based on available VRAM."""
    configs = {
        "8b": {
            "model_name": "unsloth/llama-3-8b-Instruct-bnb-4bit",
            "max_seq_length": 2048,
            "load_in_4bit": True,
        },
        "3b": {
            "model_name": "unsloth/Llama-3.2-3B-Instruct-bnb-4bit",
            "max_seq_length": 2048,
            "load_in_4bit": True,
        },
        "1b": {
            "model_name": "unsloth/Llama-3.2-1B-Instruct-bnb-4bit",
            "max_seq_length": 2048,
            "load_in_4bit": True,
        }
    }
    return configs.get(model_size, configs["3b"])


def format_training_data(data: list) -> Dataset:
    """Format instruction data for chat-style fine-tuning."""
    formatted = []
    for item in data:
        # Create chat-style prompt
        messages = [
            {"role": "system", "content": "You are an AML (Anti-Money Laundering) expert analyst. Analyze transactions and provide detailed risk assessments citing FATF recommendations and regulatory requirements."},
            {"role": "user", "content": f"{item['instruction']}\n\n{item['input']}"},
            {"role": "assistant", "content": item['output']}
        ]
        formatted.append({"messages": messages})
    return Dataset.from_list(formatted)


def train_model(args):
    """Main training function using Unsloth."""
    if not UNSLOTH_AVAILABLE:
        print("ERROR: Unsloth is not available. Please install it first.")
        return
    
    print("=" * 60)
    print("AML Expert Model Fine-tuning with Unsloth")
    print("=" * 60)
    
    # Get model config
    config = get_model_config(args.model_size)
    print(f"\nModel: {config['model_name']}")
    print(f"Max Sequence Length: {config['max_seq_length']}")
    
    # Load model with Unsloth optimizations
    print("\n[1/5] Loading base model with Unsloth...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config["model_name"],
        max_seq_length=config["max_seq_length"],
        load_in_4bit=config["load_in_4bit"],
        dtype=None,  # Auto-detect
    )
    
    # Apply LoRA adapters
    print("[2/5] Applying LoRA adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,  # LoRA rank
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                       "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",  # 2x faster
        random_state=42,
    )
    
    # Apply chat template
    tokenizer = get_chat_template(
        tokenizer,
        chat_template="llama-3",
    )
    
    # Prepare dataset
    print("[3/5] Preparing AML instruction dataset...")
    dataset = format_training_data(AML_TRAINING_DATA)
    print(f"Training samples: {len(dataset)}")
    
    def formatting_prompts_func(examples):
        convos = examples["messages"]
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convos]
        return {"text": texts}
    
    dataset = dataset.map(formatting_prompts_func, batched=True)
    
    # Training arguments
    print("[4/5] Configuring training...")
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=args.max_steps if args.max_steps > 0 else None,
        num_train_epochs=args.epochs if args.max_steps <= 0 else None,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=42,
        report_to="none",  # Disable W&B
    )
    
    # Create trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=config["max_seq_length"],
        args=training_args,
    )
    
    # Train
    print("[5/5] Training model...")
    print("-" * 40)
    trainer.train()
    print("-" * 40)
    print("Training complete!")
    
    # Save model
    print(f"\nSaving model to {args.output_dir}...")
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    
    # Also save as GGUF for Ollama
    if args.save_gguf:
        gguf_path = os.path.join(args.output_dir, "aml-expert.gguf")
        print(f"Saving GGUF format to {gguf_path}...")
        model.save_pretrained_gguf(gguf_path, tokenizer, quantization_method="q4_k_m")
    
    print("\n" + "=" * 60)
    print("FINE-TUNING COMPLETE!")
    print("=" * 60)
    print(f"Model saved to: {args.output_dir}")
    print("\nNext steps:")
    print("1. Run: python scripts/interactive_analysis.py")
    print("2. Or load in Ollama: ollama create aml-expert -f Modelfile")


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Llama-3 for AML analysis with Unsloth")
    parser.add_argument("--model_size", type=str, default="3b", choices=["1b", "3b", "8b"],
                        help="Model size to fine-tune (1b, 3b, or 8b)")
    parser.add_argument("--max_steps", type=int, default=50,
                        help="Maximum training steps (use -1 for epoch-based training)")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs (only used if max_steps <= 0)")
    parser.add_argument("--output_dir", type=str, default="./models/aml-expert",
                        help="Output directory for the fine-tuned model")
    parser.add_argument("--save_gguf", action="store_true",
                        help="Also save model in GGUF format for Ollama")
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run training
    train_model(args)


if __name__ == "__main__":
    main()
