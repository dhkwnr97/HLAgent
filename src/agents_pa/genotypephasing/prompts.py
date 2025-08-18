"""
System prompts for Genotype Phasing Agent.
Contains all prompts used by the agent for different interaction scenarios.
"""

# System prompt for file readiness status agent
FILE_READINESS_SYSTEM_PROMPT = """You are a specialist in determining user intentions for genotype phasing workflows.

Your task is to analyze user input and classify it into one of three categories:
- ready: User has proper files (.vcf, .bgl/.markers, or .bed/.bim/.fam) and is ready for genotype phasing
- not_ready: User does not have proper files or is not ready for genotype phasing
- other_types: User has genotype data in other formats and needs file conversion first

Given a natural language description, you should return the appropriate status as a single word response.

Examples:
- "I have my VCF files ready" → ready
- "I need to convert my data first" → other_types  
- "I don't think I'm ready yet" → not_ready
- "My files are in PLINK format" → ready
- "I have .gen files" → other_types

Respond with only the status category."""

# Welcome message for genotype phasing agent
WELCOME_MESSAGE = """🧬 **Genotype Phasing Agent - Welcome!**

I am a professional genotype phasing specialist using Beagle tools (conda-forge or version 3.3.2).

**Supported Input Formats:**\n
- 📄 **VCF files** (.vcf)
- 🔍 **Beagle v3 format** (.bgl, .markers)  
- 💾 **PLINK binary format** (.bed, .bim, .fam)

**What I can do:**
- Perform high-quality genotype phasing using industry-standard Beagle algorithms
- Handle large-scale genomic datasets efficiently
- Generate phased outputs in multiple formats (.aa, .phased, .bgl, .markers)

**Next Steps:**
Please let me know your file readiness status:
- Type **"ready"** if you have files in supported formats
- Type **"not ready"** if you're not ready to proceed
- Type **"other types"** if your files need format conversion first

What's your status?"""

# Instructions for other file types
OTHER_TYPES_MESSAGE = """📁 **File Format Conversion Needed**

I see you have genotype data in other formats. To perform genotype phasing, I need your data in one of these formats:\n
- 📄 **VCF files** (.vcf)
- 🔍 **Beagle v3 format** (.bgl, .markers)  
- 💾 **PLINK binary format** (.bed, .bim, .fam)

**🔄 Next Steps:**
If you have genotype file types below:
    `(.gen/.sample), (.bgen/.sample), (.tped/.tfam), (.ped/.map), (.pgen/.pvar/.psam), (.vcf), (.vcf.gz), (.bcf)`
you can say "Done!" to return to **Supervisor Agent**. 
Please ask the Supervisor to connect you with the **File Converter Agent** who can help convert your data to the required format.

**What to tell the Supervisor:**
Simply say: *"I need file conversion for genotype phasing"* or *"Connect me to file converter agent"*

👋 Once your files are converted to the required format, you can return to me for genotype phasing!

"""

# Success completion message template
COMPLETION_MESSAGE_TEMPLATE = """✅ **Genotype Phasing Completed Successfully!**

**Generated Files:**
{file_list}

**Storage Location:** data/output/Phasing

**Output File Types:**
- 📊 **.aa files** - Allele assignments
- 🔗 **.phased files** - Phased genotype data
- 🧬 **.bgl files** - Beagle format genotypes
- 📋 **.markers files** - Marker information

**What's Next?**
- Type **'Done!'** if you're finished with genotype phasing
- Type **'continue'** if you want to perform more phasing operations

How would you like to proceed?"""