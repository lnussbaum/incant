#!/bin/bash

# This is the Bash completion script for Incant

# _incant_completions: Provides autocompletion for Incant commands
_incant_completions() {
    local cur prev opts instance_names
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Commands like up, provision, destroy, list, dump
    opts="up provision destroy list dump init"


    # Handle auto-completion based on the previous command word
    case "${prev}" in
        "up"|"provision"|"destroy")
            # Fetch list of instances from the 'incant list' command
            instance_names=$(incant --quiet list)
            if [ $? -ne 0 ]; then
                COMPREPLY=( $(compgen -W "" -- ${cur}) )
                return 0
            fi
            instance_names=$(echo $instance_names | tr '\n' ' ')  # Convert the list to a space-separated string
            # Complete with instance names
            COMPREPLY=( $(compgen -W "${instance_names}" -- ${cur}) )
            return 0
            ;;
        "list"|"dump"|"init")
            # No further completion needed
            return 0
            ;;
        *)
            # Complete with the general commands (up, provision, etc.)
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
            ;;
    esac
}

# Enable completion for incant
complete -F _incant_completions incant
